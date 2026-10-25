import { describe, expect, it } from 'vitest'
import { filterNetworkMap, normalizeNetworkMap } from './networkMap'

const validNetwork = {
  dataset_id: 'demo_seed_42',
  dataset_hash: 'abc123',
  run_id: 'run_20241116_test',
  origin_date: '2024-11-16',
  locations: [
    {
      id: 'WH_01',
      type: 'warehouse',
      name: 'North Warehouse',
      region: 'North',
      latitude: 40.7,
      longitude: -74,
      coordinate_status: 'valid',
      usable_inventory: 125,
    },
    {
      id: 'DEST_001',
      type: 'store',
      name: 'Central Store',
      region: 'North',
      latitude: null,
      longitude: null,
      coordinate_status: 'missing',
      usable_inventory: 18,
      risk: {
        level: 'HIGH',
        alert_count: 1,
        expected_unmet_units: 7,
        expected_expiry_units: 0,
        minimum_days_of_cover: 1.4,
        primary_drivers: ['Low cover'],
      },
    },
  ],
  flows: [
    {
      line_id: 'L-1',
      source_id: 'WH_01',
      destination_id: 'DEST_001',
      sku_id: 'SKU_001',
      quantity: 25,
      freight_cost: 4.5,
      verification_status: 'verified',
    },
  ],
}

describe('distribution network map data', () => {
  it('normalizes valid coordinates and optimizer shipment references', () => {
    const result = normalizeNetworkMap(validNetwork)
    expect(result.locations[0]).toMatchObject({
      id: 'WH_01',
      latitude: 40.7,
      longitude: -74,
      coordinateStatus: 'valid',
    })
    expect(result.locations[1].coordinateStatus).toBe('missing')
    expect(result.flows[0]).toMatchObject({
      lineId: 'L-1',
      sourceId: 'WH_01',
      destinationId: 'DEST_001',
      quantity: 25,
      freightCost: 4.5,
    })
  })

  it('rejects coordinates outside geographic ranges without plotting them', () => {
    const response = {
      ...validNetwork,
      locations: validNetwork.locations.map((location) => (
        location.id === 'WH_01'
          ? { ...location, latitude: 91 }
          : location
      )),
    }
    const result = normalizeNetworkMap(response)
    expect(result.locations[0]).toMatchObject({
      latitude: null,
      longitude: null,
      coordinateStatus: 'invalid',
    })
  })

  it('treats partially returned coordinates as invalid', () => {
    const response = {
      ...validNetwork,
      locations: validNetwork.locations.map((location) => (
        location.id === 'WH_01'
          ? { ...location, longitude: null }
          : location
      )),
    }
    const result = normalizeNetworkMap(response)
    expect(result.locations[0]).toMatchObject({
      latitude: null,
      longitude: null,
      coordinateStatus: 'invalid',
    })
  })

  it('rejects shipment lines with unknown or wrong-type endpoints', () => {
    const response = {
      ...validNetwork,
      flows: [{ ...validNetwork.flows[0], source_id: 'UNKNOWN' }],
    }
    expect(() => normalizeNetworkMap(response)).toThrow(/invalid location references/)
  })

  it('filters locations and flows by SKU, risk, and warehouse', () => {
    const normalized = normalizeNetworkMap(validNetwork)
    const result = filterNetworkMap(normalized, {
      search: '',
      sku: 'SKU_001',
      warehouse: 'WH_01',
      destination: 'ALL',
      risk: 'HIGH',
      status: 'verified',
    })
    expect(result.flows.map((flow) => flow.lineId)).toEqual(['L-1'])
    expect(result.locations.map((location) => location.id)).toEqual(['WH_01', 'DEST_001'])
  })

  it('returns an empty shipment set when the selected run has no flows', () => {
    const result = normalizeNetworkMap({ ...validNetwork, flows: [] })
    expect(result.flows).toEqual([])
    expect(result.locations).toHaveLength(2)
  })
})
