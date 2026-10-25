const LOCATION_TYPES = new Set(['warehouse', 'distributor', 'store'])
const RISK_LEVELS = new Set(['HIGH', 'MEDIUM', 'LOW'])
const VERIFICATION_STATUSES = new Set(['verified', 'unverified'])

function isValidCoordinate(latitude, longitude) {
  return Number.isFinite(latitude)
    && Number.isFinite(longitude)
    && latitude >= -90
    && latitude <= 90
    && longitude >= -180
    && longitude <= 180
}

export function normalizeNetworkMap(response) {
  if (
    !response
    || typeof response.dataset_id !== 'string'
    || typeof response.run_id !== 'string'
    || typeof response.dataset_hash !== 'string'
    || typeof response.origin_date !== 'string'
    || !Array.isArray(response.locations)
    || !Array.isArray(response.flows)
  ) {
    throw new Error('The backend returned an invalid distribution network response.')
  }

  const locations = response.locations.map((location) => {
    if (
      !location
      || typeof location.id !== 'string'
      || !location.id
      || !LOCATION_TYPES.has(location.type)
      || typeof location.name !== 'string'
    ) {
      throw new Error('The backend returned a location with invalid identity or type.')
    }
    const parseCoordinate = (value) => (
      value == null || (typeof value === 'string' && !value.trim())
        ? null
        : Number(value)
    )
    const latitude = parseCoordinate(location.latitude)
    const longitude = parseCoordinate(location.longitude)
    const hasCoordinates = latitude != null && longitude != null
    const coordinateStatus = hasCoordinates && isValidCoordinate(latitude, longitude)
      ? 'valid'
      : location.coordinate_status === 'invalid'
        || latitude != null
        || longitude != null
        || (hasCoordinates && !isValidCoordinate(latitude, longitude))
        ? 'invalid'
        : 'missing'

    return {
      id: location.id,
      type: location.type,
      name: location.name,
      region: location.region ?? '',
      latitude: coordinateStatus === 'valid' ? latitude : null,
      longitude: coordinateStatus === 'valid' ? longitude : null,
      coordinateStatus,
      usableInventory: location.usable_inventory != null && Number.isFinite(Number(location.usable_inventory))
        ? Number(location.usable_inventory)
        : null,
      risk: location.risk && RISK_LEVELS.has(location.risk.level)
        ? {
            level: location.risk.level,
            alertCount: Number.isFinite(Number(location.risk.alert_count))
              ? Number(location.risk.alert_count)
              : 0,
            expectedUnmetUnits: location.risk.expected_unmet_units != null
              && Number.isFinite(Number(location.risk.expected_unmet_units))
              ? Number(location.risk.expected_unmet_units)
              : null,
            expectedExpiryUnits: location.risk.expected_expiry_units != null
              && Number.isFinite(Number(location.risk.expected_expiry_units))
              ? Number(location.risk.expected_expiry_units)
              : null,
            minimumDaysOfCover: location.risk.minimum_days_of_cover != null
              && Number.isFinite(Number(location.risk.minimum_days_of_cover))
              ? Number(location.risk.minimum_days_of_cover)
              : null,
            primaryDrivers: Array.isArray(location.risk.primary_drivers)
              ? location.risk.primary_drivers.filter((driver) => typeof driver === 'string')
              : [],
          }
        : null,
    }
  })
  const locationById = new Map(locations.map((location) => [location.id, location]))
  if (locationById.size !== locations.length) {
    throw new Error('The backend returned duplicate location identifiers.')
  }

  const flowIds = new Set()
  const flows = response.flows.map((flow) => {
    if (!flow || typeof flow !== 'object') {
      throw new Error('The backend returned a shipment with invalid location references or values.')
    }
    const source = locationById.get(flow.source_id)
    const destination = locationById.get(flow.destination_id)
    const quantity = Number(flow.quantity)
    const freightCost = flow.freight_cost == null ? null : Number(flow.freight_cost)
    if (
      !flow
      || typeof flow.line_id !== 'string'
      || !flow.line_id
      || flowIds.has(flow.line_id)
      || typeof flow.sku_id !== 'string'
      || source?.type !== 'warehouse'
      || !['distributor', 'store'].includes(destination?.type)
      || !Number.isFinite(quantity)
      || quantity <= 0
      || (freightCost != null && (!Number.isFinite(freightCost) || freightCost < 0))
      || !VERIFICATION_STATUSES.has(flow.verification_status)
    ) {
      throw new Error('The backend returned a shipment with invalid location references or values.')
    }
    flowIds.add(flow.line_id)
    return {
      lineId: flow.line_id,
      sourceId: flow.source_id,
      destinationId: flow.destination_id,
      skuId: flow.sku_id,
      quantity,
      freightCost,
      verificationStatus: flow.verification_status,
    }
  })

  return {
    datasetId: response.dataset_id,
    datasetHash: response.dataset_hash,
    runId: response.run_id,
    originDate: response.origin_date,
    locations,
    flows,
  }
}

export function filterNetworkMap(network, filters) {
  const locationsById = new Map(network.locations.map((location) => [location.id, location]))
  const query = filters.search.trim().toLowerCase()
  const locationsMatchingSearch = new Set(
    network.locations
      .filter((location) => (
        !query
        || location.id.toLowerCase().includes(query)
        || location.name.toLowerCase().includes(query)
      ))
      .map((location) => location.id)
  )

  const flows = network.flows.filter((flow) => {
    const destination = locationsById.get(flow.destinationId)
    return (
      (filters.sku === 'ALL' || flow.skuId === filters.sku)
      && (filters.warehouse === 'ALL' || flow.sourceId === filters.warehouse)
      && (filters.destination === 'ALL' || flow.destinationId === filters.destination)
      && (filters.status === 'ALL' || flow.verificationStatus === filters.status)
      && (
        filters.risk === 'ALL'
        || destination?.risk?.level === filters.risk
      )
      && (
        !query
        || locationsMatchingSearch.has(flow.sourceId)
        || locationsMatchingSearch.has(flow.destinationId)
      )
    )
  })
  const visibleIds = new Set(flows.flatMap((flow) => [flow.sourceId, flow.destinationId]))
  const hasFilters = query
    || filters.sku !== 'ALL'
    || filters.warehouse !== 'ALL'
    || filters.destination !== 'ALL'
    || filters.risk !== 'ALL'
    || filters.status !== 'ALL'

  const locations = network.locations.filter((location) => {
    if (!hasFilters) return true
    const selectedWarehouse = filters.warehouse === 'ALL'
      || location.id === filters.warehouse
    const selectedDestination = filters.destination === 'ALL'
      || location.id === filters.destination
    const selectedRisk = filters.risk === 'ALL'
      || location.risk?.level === filters.risk
    const selectedSearch = !query || locationsMatchingSearch.has(location.id)
    const directMatch = selectedWarehouse && selectedDestination && selectedRisk && selectedSearch
    return directMatch || visibleIds.has(location.id)
  })

  return { locations, flows }
}
