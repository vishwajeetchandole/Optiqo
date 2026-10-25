import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  CircleMarker,
  MapContainer,
  Polyline,
  Popup,
  TileLayer,
  ZoomControl,
  useMap,
} from 'react-leaflet'
import {
  AlertTriangle,
  Crosshair,
  MapPin,
  RotateCcw,
  Search,
} from 'lucide-react'
import { SectionCard } from '@/components/shared/SectionCard'
import { getRunNetwork } from '@/services/networkMap'
import { filterNetworkMap } from '@/lib/networkMap'
import { cn } from '@/lib/utils'
import 'leaflet/dist/leaflet.css'

const DEFAULT_FILTERS = {
  search: '',
  sku: 'ALL',
  warehouse: 'ALL',
  destination: 'ALL',
  risk: 'ALL',
  status: 'ALL',
}

const LOCATION_STYLE = {
  warehouse: { color: '#6753D8', radius: 9, label: 'Warehouse / distribution center' },
  distributor: { color: '#D97706', radius: 7, label: 'Distributor' },
  store: { color: '#138A61', radius: 6, label: 'Retail store' },
}

const RISK_STYLE = {
  HIGH: '#DC2626',
  MEDIUM: '#D97706',
  LOW: '#138A61',
}

function numberLabel(value) {
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 1 })
}

function NetworkBounds({ locations, fitRequest }) {
  const map = useMap()

  useEffect(() => {
    const points = locations
      .filter((location) => Number.isFinite(location.latitude) && Number.isFinite(location.longitude))
      .map((location) => [location.latitude, location.longitude])
    if (!points.length) return
    if (points.length === 1) {
      map.setView(points[0], 8)
    } else {
      map.fitBounds(points, { padding: [32, 32], maxZoom: 11 })
    }
  }, [locations, fitRequest, map])

  return null
}

function LocationDetails({ location }) {
  if (!location) {
    return <p className="text-xs text-muted">Select a map marker or location to inspect its dataset details.</p>
  }
  const typeLabel = LOCATION_STYLE[location.type]?.label ?? location.type
  return (
    <div className="space-y-2 text-xs">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-semibold text-ink">{location.name}</p>
          <p className="font-mono text-muted">{location.id}</p>
        </div>
        <span className="rounded-full bg-[var(--color-tint)] px-2 py-1 text-[10px] text-ink">
          {typeLabel}
        </span>
      </div>
      <p className="text-muted">Region: {location.region || 'Unavailable'}</p>
      <p className="text-muted">
        Usable inventory: {location.usableInventory == null
          ? 'Unavailable'
          : `${numberLabel(location.usableInventory)} units`}
      </p>
      {location.type !== 'warehouse' && (
        <p className="text-muted">Demand / forecast: Unavailable from the selected-run network response.</p>
      )}
      {location.risk ? (
        <div className="space-y-1 border-t border-token pt-2">
          <p className="flex items-center gap-1.5 font-semibold text-ink">
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: RISK_STYLE[location.risk.level] }} />
            Pre-plan {location.risk.level} risk · {location.risk.alertCount} SKU alerts
          </p>
          <p className="text-muted">
            Expected unmet: {location.risk.expectedUnmetUnits == null
              ? 'Unavailable'
              : `${numberLabel(location.risk.expectedUnmetUnits)} units`}
          </p>
          <p className="text-muted">
            Expected expiry: {location.risk.expectedExpiryUnits == null
              ? 'Unavailable'
              : `${numberLabel(location.risk.expectedExpiryUnits)} units`}
          </p>
          <p className="text-muted">
            Minimum days of cover: {location.risk.minimumDaysOfCover == null
              ? 'Unavailable'
              : numberLabel(location.risk.minimumDaysOfCover)}
          </p>
          {location.risk.primaryDrivers.map((driver) => (
            <p key={driver} className="text-muted">{driver}</p>
          ))}
        </div>
      ) : location.type === 'warehouse' ? (
        <p className="text-muted">No warehouse-specific risk summary is available.</p>
      ) : (
        <p className="text-muted">No destination risk alerts were returned for this location.</p>
      )}
    </div>
  )
}

function FlowDetails({ flow, locationById }) {
  if (!flow) {
    return <p className="text-xs text-muted">Select an allocation line to inspect its shipment details.</p>
  }
  const source = locationById.get(flow.sourceId)
  const destination = locationById.get(flow.destinationId)
  return (
    <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
      <span className="text-muted">Source</span>
      <span className="text-right text-ink">{source?.name ?? flow.sourceId} ({flow.sourceId})</span>
      <span className="text-muted">Destination</span>
      <span className="text-right text-ink">{destination?.name ?? flow.destinationId} ({flow.destinationId})</span>
      <span className="text-muted">SKU</span>
      <span className="text-right font-mono text-ink">{flow.skuId}</span>
      <span className="text-muted">Quantity</span>
      <span className="text-right font-mono text-ink">{numberLabel(flow.quantity)} units</span>
      <span className="text-muted">Freight cost</span>
      <span className="text-right font-mono text-ink">
        {flow.freightCost == null ? 'Unavailable' : numberLabel(flow.freightCost)}
      </span>
      <span className="text-muted">Run verification</span>
      <span className="text-right capitalize text-ink">{flow.verificationStatus}</span>
    </div>
  )
}

function FilterSelect({ label, value, onChange, options }) {
  return (
    <label className="flex min-w-0 flex-col gap-1 text-[10px] font-semibold uppercase tracking-wide text-muted">
      {label}
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-9 min-w-0 rounded-lg border border-token bg-[var(--color-surface)] px-2 text-xs font-normal normal-case tracking-normal text-ink"
      >
        <option value="ALL">All</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
    </label>
  )
}

export default function NetworkMapPanel({ runId, selectedLineId, onSelectLine }) {
  const [networkState, setNetworkState] = useState(null)
  const [filters, setFilters] = useState(DEFAULT_FILTERS)
  const [selectedLocationId, setSelectedLocationId] = useState(null)
  const [selectedFlowId, setSelectedFlowId] = useState(selectedLineId)
  const [fitRequest, setFitRequest] = useState(0)
  const [tileError, setTileError] = useState(false)
  const [manualCoordinateState, setManualCoordinateState] = useState({
    datasetHash: null,
    values: {},
  })
  const [mappingLocationId, setMappingLocationId] = useState('')
  const [latitudeInput, setLatitudeInput] = useState('')
  const [longitudeInput, setLongitudeInput] = useState('')
  const [mappingError, setMappingError] = useState(null)

  useEffect(() => {
    let active = true
    if (!runId) return () => { active = false }
    getRunNetwork({ runId }).then((result) => {
      if (!active) return
      let mapping = { values: {}, error: null }
      try {
        const stored = window.localStorage.getItem(
          `optiqo-map-coordinates:${result.datasetHash}`
        )
        if (stored) {
          const parsed = JSON.parse(stored)
          if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
            mapping.values = parsed
          } else {
            mapping.error = 'Saved coordinate mappings have an invalid format.'
          }
        }
      } catch {
        mapping.error = 'Saved coordinate mappings could not be read from this browser.'
      }
      setManualCoordinateState({
        datasetHash: result.datasetHash,
        values: mapping.values,
      })
      setMappingError(mapping.error)
      setNetworkState({ runId, network: result, loading: false, error: null })
    }).catch((requestError) => {
      if (active) {
        setNetworkState({
          runId,
          network: null,
          loading: false,
          error: requestError?.message || 'Unable to load the selected run network.',
        })
      }
    })
    return () => { active = false }
  }, [runId])

  const network = networkState?.runId === runId ? networkState.network : null
  const loading = Boolean(runId) && (
    networkState?.runId !== runId || networkState.loading
  )
  const error = !runId
    ? 'Generate or select a planning run to view its distribution network.'
    : networkState?.runId === runId
      ? networkState.error
      : null

  const manualCoordinates = useMemo(
    () => manualCoordinateState.datasetHash === network?.datasetHash
      ? manualCoordinateState.values
      : {},
    [manualCoordinateState, network?.datasetHash]
  )

  const locations = useMemo(() => {
    if (!network) return []
    return network.locations.map((location) => {
      const manual = manualCoordinates[location.id]
      if (
        manual
        && Number.isFinite(manual.latitude)
        && Number.isFinite(manual.longitude)
        && manual.latitude >= -90
        && manual.latitude <= 90
        && manual.longitude >= -180
        && manual.longitude <= 180
      ) {
        return {
          ...location,
          latitude: manual.latitude,
          longitude: manual.longitude,
          coordinateStatus: 'valid',
          coordinateSource: 'User supplied',
        }
      }
      return {
        ...location,
        coordinateSource: location.coordinateStatus === 'valid' ? 'Dataset' : null,
      }
    })
  }, [network, manualCoordinates])

  const normalizedNetwork = useMemo(
    () => network ? { ...network, locations } : null,
    [network, locations]
  )
  const filtered = useMemo(
    () => normalizedNetwork ? filterNetworkMap(normalizedNetwork, filters) : { locations: [], flows: [] },
    [normalizedNetwork, filters]
  )
  const plottedLocations = useMemo(
    () => filtered.locations.filter((location) => location.coordinateStatus === 'valid'),
    [filtered.locations]
  )
  const unplottedLocations = useMemo(
    () => filtered.locations.filter((location) => location.coordinateStatus !== 'valid'),
    [filtered.locations]
  )
  const locationById = useMemo(
    () => new Map(locations.map((location) => [location.id, location])),
    [locations]
  )
  const selectedLocation = locations.find((location) => location.id === selectedLocationId)
  const selectedFlow = filtered.flows.find((flow) => flow.lineId === (selectedLineId || selectedFlowId))
    ?? filtered.flows.find((flow) => flow.lineId === selectedFlowId)

  const skus = useMemo(
    () => [...new Set(network?.flows.map((flow) => flow.skuId) ?? [])].sort(),
    [network]
  )
  const warehouses = useMemo(
    () => locations.filter((location) => location.type === 'warehouse'),
    [locations]
  )
  const destinations = useMemo(
    () => locations.filter((location) => location.type !== 'warehouse'),
    [locations]
  )

  const updateFilter = (key, value) => setFilters((current) => ({ ...current, [key]: value }))

  const handleMappingLocationChange = (locationId) => {
    setMappingLocationId(locationId)
    const mappedLocation = locations.find((location) => location.id === locationId)
    setLatitudeInput(mappedLocation?.latitude == null ? '' : String(mappedLocation.latitude))
    setLongitudeInput(mappedLocation?.longitude == null ? '' : String(mappedLocation.longitude))
  }

  const selectFlow = useCallback((flow) => {
    setSelectedFlowId(flow.lineId)
    setSelectedLocationId(null)
    onSelectLine?.(flow.lineId)
  }, [onSelectLine])

  const selectLocation = useCallback((locationId) => {
    setSelectedLocationId(locationId)
    setSelectedFlowId(null)
    onSelectLine?.(null)
  }, [onSelectLine])

  const saveManualCoordinates = (event) => {
    event.preventDefault()
    const latitude = Number(latitudeInput)
    const longitude = Number(longitudeInput)
    if (
      !mappingLocationId
      || !Number.isFinite(latitude)
      || !Number.isFinite(longitude)
      || latitude < -90
      || latitude > 90
      || longitude < -180
      || longitude > 180
    ) {
      setMappingError('Enter a valid latitude (-90 to 90) and longitude (-180 to 180).')
      return
    }
    const updated = {
      ...manualCoordinates,
      [mappingLocationId]: { latitude, longitude },
    }
    setManualCoordinateState({ datasetHash: network.datasetHash, values: updated })
    setMappingError(null)
    try {
      window.localStorage.setItem(
        `optiqo-map-coordinates:${network.datasetHash}`,
        JSON.stringify(updated)
      )
    } catch {
      setMappingError('Coordinates were applied for this view but could not be saved in this browser.')
    }
    setFitRequest((request) => request + 1)
  }

  const clearManualCoordinates = () => {
    if (!mappingLocationId) return
    const updated = { ...manualCoordinates }
    delete updated[mappingLocationId]
    setManualCoordinateState({ datasetHash: network.datasetHash, values: updated })
    setMappingError(null)
    try {
      window.localStorage.setItem(
        `optiqo-map-coordinates:${network.datasetHash}`,
        JSON.stringify(updated)
      )
    } catch {
      setMappingError('The mapping was removed for this view but could not be saved in this browser.')
    }
  }

  const resetFilters = () => {
    setFilters(DEFAULT_FILTERS)
    setSelectedLocationId(null)
    setSelectedFlowId(null)
  }

  return (
    <SectionCard
      title="Distribution Network Map"
      subtitle={network
        ? `Allocation view · ${network.datasetId} · run ${network.runId}`
        : 'Warehouse, destination and optimizer-allocation view'}
      className="overflow-hidden"
      bodyClassName="space-y-4"
    >
      {loading ? (
        <div className="flex h-56 items-center justify-center text-sm text-muted" role="status">
          Loading dataset locations and plan allocations…
        </div>
      ) : error ? (
        <div className="flex min-h-40 items-center gap-3 rounded-xl border border-red-300 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/30 dark:text-red-200" role="alert">
          <AlertTriangle className="h-5 w-5 flex-shrink-0" />
          <div>
            <p className="font-semibold">Network map unavailable</p>
            <p className="mt-1">{error}</p>
          </div>
        </div>
      ) : network ? (
        <>
          <div className="flex flex-wrap items-end justify-between gap-3 rounded-xl border border-token bg-[var(--color-surface-subtle)] p-3">
            <label className="flex min-w-48 flex-1 flex-col gap-1 text-[10px] font-semibold uppercase tracking-wide text-muted">
              Search locations
              <span className="relative">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted" />
                <input
                  value={filters.search}
                  onChange={(event) => updateFilter('search', event.target.value)}
                  placeholder="Name or location ID"
                  className="h-9 w-full rounded-lg border border-token bg-[var(--color-surface)] pl-8 pr-3 text-xs font-normal normal-case tracking-normal text-ink"
                />
              </span>
            </label>
            <FilterSelect label="Product / SKU" value={filters.sku} onChange={(value) => updateFilter('sku', value)} options={skus.map((sku) => ({ value: sku, label: sku }))} />
            <FilterSelect label="Warehouse" value={filters.warehouse} onChange={(value) => updateFilter('warehouse', value)} options={warehouses.map((location) => ({ value: location.id, label: `${location.id} · ${location.name}` }))} />
            <FilterSelect label="Destination" value={filters.destination} onChange={(value) => updateFilter('destination', value)} options={destinations.map((location) => ({ value: location.id, label: `${location.id} · ${location.name}` }))} />
            <FilterSelect label="Risk level" value={filters.risk} onChange={(value) => updateFilter('risk', value)} options={['HIGH', 'MEDIUM', 'LOW'].map((risk) => ({ value: risk, label: risk }))} />
            <FilterSelect label="Run verification" value={filters.status} onChange={(value) => updateFilter('status', value)} options={[...new Set(network.flows.map((flow) => flow.verificationStatus))].map((status) => ({ value: status, label: status }))} />
            <button type="button" onClick={resetFilters} className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-token px-3 text-xs text-ink hover:bg-[var(--color-tint)]">
              <RotateCcw className="h-3.5 w-3.5" /> Reset filters
            </button>
          </div>

          <p className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-[11px] text-blue-900 dark:border-blue-900 dark:bg-blue-950/30 dark:text-blue-100">
            Lines show optimizer allocation connections only; they are not road routes, travel times, or routing recommendations.
          </p>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.8fr)_minmax(260px,1fr)]">
            <div className="min-w-0">
              <div className="relative overflow-hidden rounded-xl border border-token bg-slate-100 dark:bg-slate-900">
                {plottedLocations.length ? (
                  <>
                    <MapContainer
                      center={[plottedLocations[0].latitude, plottedLocations[0].longitude]}
                      zoom={5}
                      zoomControl={false}
                      className="h-[380px] w-full sm:h-[460px]"
                    >
                      <TileLayer
                        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                        eventHandlers={{ tileerror: () => setTileError(true) }}
                      />
                      <ZoomControl position="topright" />
                      <NetworkBounds locations={plottedLocations} fitRequest={fitRequest} />
                      {filtered.flows.map((flow) => {
                        const source = locationById.get(flow.sourceId)
                        const destination = locationById.get(flow.destinationId)
                        if (
                          source?.coordinateStatus !== 'valid'
                          || destination?.coordinateStatus !== 'valid'
                        ) return null
                        const isSelected = flow.lineId === (selectedLineId || selectedFlowId)
                        return (
                          <Polyline
                            key={flow.lineId}
                            positions={[
                              [source.latitude, source.longitude],
                              [destination.latitude, destination.longitude],
                            ]}
                            pathOptions={{
                              color: isSelected ? '#DC2626' : '#7060D8',
                              opacity: isSelected ? 0.95 : 0.48,
                              weight: Math.min(8, 2 + Math.log10(flow.quantity + 1)),
                            }}
                            eventHandlers={{ click: () => selectFlow(flow) }}
                          >
                            <Popup>
                              <strong>{flow.skuId}</strong><br />
                              {numberLabel(flow.quantity)} units · {flow.lineId}<br />
                              Freight cost: {flow.freightCost == null ? 'Unavailable' : numberLabel(flow.freightCost)}
                            </Popup>
                          </Polyline>
                        )
                      })}
                      {plottedLocations.map((location) => {
                        const style = LOCATION_STYLE[location.type]
                        const isEndpoint = selectedFlow
                          && [selectedFlow.sourceId, selectedFlow.destinationId].includes(location.id)
                        const fillColor = location.risk?.level
                          ? RISK_STYLE[location.risk.level]
                          : style.color
                        return (
                          <CircleMarker
                            key={location.id}
                            center={[location.latitude, location.longitude]}
                            radius={isEndpoint ? style.radius + 3 : style.radius}
                            pathOptions={{
                              color: isEndpoint ? '#DC2626' : fillColor,
                              fillColor,
                              fillOpacity: 0.9,
                              weight: isEndpoint ? 3 : 2,
                            }}
                            eventHandlers={{
                              click: () => selectLocation(location.id),
                            }}
                          >
                            <Popup>
                              <strong>{location.name}</strong><br />
                              {location.id} · {style.label}<br />
                              Usable inventory: {location.usableInventory == null ? 'Unavailable' : `${numberLabel(location.usableInventory)} units`}<br />
                              {location.risk ? `Risk: ${location.risk.level}` : 'Risk: unavailable'}
                            </Popup>
                          </CircleMarker>
                        )
                      })}
                    </MapContainer>
                    <button
                      type="button"
                      onClick={() => setFitRequest((request) => request + 1)}
                      className="absolute left-3 top-3 z-[1000] inline-flex items-center gap-1.5 rounded-lg border border-token bg-[var(--color-surface)] px-3 py-2 text-xs font-medium text-ink shadow"
                      aria-label="Fit map to plotted network"
                    >
                      <Crosshair className="h-3.5 w-3.5" /> Fit network
                    </button>
                  </>
                ) : (
                  <div className="flex h-[380px] flex-col items-center justify-center gap-2 px-6 text-center sm:h-[460px]">
                    <MapPin className="h-7 w-7 text-muted" />
                    <p className="text-sm font-semibold text-ink">No locations have valid coordinates</p>
                    <p className="max-w-md text-xs text-muted">
                      Nothing is plotted at an assumed position. Use the optional coordinate-mapping workflow below, or add valid latitude and longitude fields to your dataset.
                    </p>
                  </div>
                )}
                {tileError && plottedLocations.length > 0 && (
                  <div role="status" className="absolute bottom-3 left-3 right-3 z-[1000] rounded-lg bg-amber-100 px-3 py-2 text-xs text-amber-900 shadow">
                    OpenStreetMap tiles could not be loaded. Markers and optimizer allocation lines remain available.
                  </div>
                )}
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-[10px] text-muted" aria-label="Map legend">
                {Object.entries(LOCATION_STYLE).map(([type, style]) => (
                  <span key={type} className="inline-flex items-center gap-1.5">
                    <span className="h-3 w-3 rounded-full border-2" style={{ background: style.color, borderColor: style.color }} />
                    {style.label}
                  </span>
                ))}
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-1 w-5 rounded bg-[#7060D8]" /> Optimizer allocation (width ∝ quantity)
                </span>
                <span>Marker color uses destination risk when available.</span>
                {Object.entries(RISK_STYLE).map(([risk, color]) => (
                  <span key={risk} className="inline-flex items-center gap-1">
                    <span className="h-2 w-2 rounded-full" style={{ background: color }} />
                    {risk} risk
                  </span>
                ))}
              </div>
            </div>

            <aside className="space-y-4">
              <div className="rounded-xl border border-token p-3">
                <h3 className="mb-3 text-xs font-semibold text-ink">Selected location</h3>
                <LocationDetails location={selectedLocation} />
              </div>
              <div className="rounded-xl border border-token p-3">
                <h3 className="mb-3 text-xs font-semibold text-ink">Selected shipment</h3>
                <FlowDetails flow={selectedFlow} locationById={locationById} />
              </div>
              <div className="rounded-xl border border-token p-3">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <h3 className="text-xs font-semibold text-ink">Locations ({filtered.locations.length})</h3>
                  <span className="text-[10px] text-muted">{unplottedLocations.length} not plotted</span>
                </div>
                <ul className="max-h-48 space-y-1 overflow-y-auto">
                  {filtered.locations.map((location) => (
                    <li key={location.id}>
                      <button
                        type="button"
                        onClick={() => {
                          selectLocation(location.id)
                          handleMappingLocationChange(location.id)
                        }}
                        className={cn(
                          'flex w-full items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-left text-[11px] hover:bg-[var(--color-tint)]',
                          selectedLocationId === location.id && 'bg-[var(--color-tint)]'
                        )}
                      >
                        <span className="min-w-0 truncate text-ink">
                          <span className="font-mono">{location.id}</span> · {location.name}
                        </span>
                        <span className={location.coordinateStatus === 'valid' ? 'text-emerald-700' : 'text-amber-700'}>
                          {location.coordinateStatus === 'valid' ? 'Plotted' : 'No coordinates'}
                        </span>
                      </button>
                    </li>
                  ))}
                  {!filtered.locations.length && (
                    <li className="py-2 text-xs text-muted">No locations match these filters.</li>
                  )}
                </ul>
              </div>
            </aside>
          </div>

          <div className="rounded-xl border border-token p-3">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div>
                <h3 className="text-xs font-semibold text-ink">Optional coordinate mapping</h3>
                <p className="mt-1 text-[10px] text-muted">
                  Enter verified coordinates yourself. Values are saved only in this browser for this dataset; no geocoding service is called.
                </p>
              </div>
              <span className="text-[10px] text-muted">Dataset coordinates take precedence unless overridden.</span>
            </div>
            <form onSubmit={saveManualCoordinates} className="grid grid-cols-1 gap-2 sm:grid-cols-[minmax(0,1fr)_140px_140px_auto_auto] sm:items-end">
              <label className="flex flex-col gap-1 text-[10px] font-semibold uppercase tracking-wide text-muted">
                Location
                <select
                  value={mappingLocationId}
                  onChange={(event) => handleMappingLocationChange(event.target.value)}
                  className="h-9 rounded-lg border border-token bg-[var(--color-surface)] px-2 text-xs font-normal normal-case tracking-normal text-ink"
                >
                  <option value="">Select a location</option>
                  {locations.map((location) => (
                    <option key={location.id} value={location.id}>{location.id} · {location.name}</option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-[10px] font-semibold uppercase tracking-wide text-muted">
                Latitude
                <input
                  type="number"
                  min="-90"
                  max="90"
                  step="any"
                  value={latitudeInput}
                  onChange={(event) => setLatitudeInput(event.target.value)}
                  className="h-9 rounded-lg border border-token bg-[var(--color-surface)] px-2 text-xs font-normal normal-case tracking-normal text-ink"
                />
              </label>
              <label className="flex flex-col gap-1 text-[10px] font-semibold uppercase tracking-wide text-muted">
                Longitude
                <input
                  type="number"
                  min="-180"
                  max="180"
                  step="any"
                  value={longitudeInput}
                  onChange={(event) => setLongitudeInput(event.target.value)}
                  className="h-9 rounded-lg border border-token bg-[var(--color-surface)] px-2 text-xs font-normal normal-case tracking-normal text-ink"
                />
              </label>
              <button type="submit" disabled={!mappingLocationId} className="h-9 rounded-lg bg-[var(--color-primary)] px-3 text-xs font-semibold text-white disabled:opacity-50">
                Save coordinates
              </button>
              {manualCoordinates[mappingLocationId] && (
                <button type="button" onClick={clearManualCoordinates} className="h-9 rounded-lg border border-token px-3 text-xs text-ink">
                  Clear mapping
                </button>
              )}
            </form>
            <p className="mt-2 text-[10px] text-muted">Coordinates must be accurate and verified. Map points are not geocoded or inferred from city or region names.</p>
            {mappingError && <p role="alert" className="mt-2 text-xs text-red-700">{mappingError}</p>}
          </div>

          <section className="overflow-hidden rounded-xl border border-token">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-token px-3 py-3">
              <div>
                <h3 className="text-xs font-semibold text-ink">Selected run allocation flows</h3>
                <p className="text-[10px] text-muted">
                  {filtered.flows.length} of {network.flows.length} optimizer shipment lines · run {network.runId}
                </p>
              </div>
              {!network.flows.length && (
                <span className="rounded-full bg-[var(--color-tint)] px-2.5 py-1 text-[10px] text-muted">No shipments in this plan</span>
              )}
            </div>
            {filtered.flows.length ? (
              <div className="max-h-64 overflow-auto">
                <table className="w-full min-w-[600px] text-left text-[11px]">
                  <thead className="sticky top-0 bg-[var(--color-surface-subtle)] text-muted">
                    <tr>
                      <th className="px-3 py-2 font-semibold">Plan line</th>
                      <th className="px-3 py-2 font-semibold">SKU</th>
                      <th className="px-3 py-2 font-semibold">Source → destination</th>
                      <th className="px-3 py-2 text-right font-semibold">Quantity</th>
                      <th className="px-3 py-2 text-right font-semibold">Freight cost</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--color-border)]">
                    {filtered.flows.map((flow) => (
                      <tr key={flow.lineId} className={flow.lineId === selectedFlowId ? 'bg-[var(--color-tint)]' : ''}>
                        <td className="px-3 py-2">
                          <button type="button" onClick={() => selectFlow(flow)} className="font-mono text-primary hover:underline">{flow.lineId}</button>
                        </td>
                        <td className="px-3 py-2 font-mono text-ink">{flow.skuId}</td>
                        <td className="px-3 py-2 text-ink">{flow.sourceId} → {flow.destinationId}</td>
                        <td className="px-3 py-2 text-right font-mono text-ink">{numberLabel(flow.quantity)}</td>
                        <td className="px-3 py-2 text-right font-mono text-ink">{flow.freightCost == null ? 'Unavailable' : numberLabel(flow.freightCost)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="px-3 py-5 text-center text-xs text-muted">
                {network.flows.length
                  ? 'No shipment lines match the current filters.'
                  : 'This selected optimization run contains no shipment lines.'}
              </div>
            )}
          </section>
        </>
      ) : null}
    </SectionCard>
  )
}
