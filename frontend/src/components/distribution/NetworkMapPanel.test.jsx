import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import NetworkMapPanel from './NetworkMapPanel'
import { getRunNetwork } from '@/services/networkMap'

vi.mock('@/services/networkMap', () => ({ getRunNetwork: vi.fn() }))
vi.mock('react-leaflet', () => ({
  CircleMarker: ({ center, children, eventHandlers }) => (
    <button
      type="button"
      aria-label={`Map marker ${center.join(',')}`}
      onClick={() => eventHandlers?.click?.()}
    >
      {children}
    </button>
  ),
  MapContainer: ({ children, className }) => <div className={className}>{children}</div>,
  Polyline: ({ children, eventHandlers }) => (
    <button type="button" aria-label="Allocation flow" onClick={() => eventHandlers?.click?.()}>
      {children}
    </button>
  ),
  Popup: ({ children }) => <span>{children}</span>,
  TileLayer: () => null,
  ZoomControl: () => null,
  useMap: () => ({ fitBounds: vi.fn(), setView: vi.fn() }),
}))

afterEach(() => {
  cleanup()
  vi.resetAllMocks()
})

const makeNetwork = (runId, hasCoordinates = true, hasFlows = true) => ({
  datasetId: 'demo_seed_42',
  datasetHash: 'dataset-hash',
  runId,
  originDate: '2024-11-16',
  locations: [
    {
      id: 'WH_01',
      type: 'warehouse',
      name: 'North Warehouse',
      region: 'North',
      latitude: hasCoordinates ? 40.7 : null,
      longitude: hasCoordinates ? -74 : null,
      coordinateStatus: hasCoordinates ? 'valid' : 'missing',
      usableInventory: 100,
      risk: null,
    },
    {
      id: 'DEST_001',
      type: 'store',
      name: 'Central Store',
      region: 'North',
      latitude: hasCoordinates ? 41 : null,
      longitude: hasCoordinates ? -73 : null,
      coordinateStatus: hasCoordinates ? 'valid' : 'missing',
      usableInventory: 20,
      risk: {
        level: 'HIGH',
        alertCount: 1,
        expectedUnmetUnits: 5,
        expectedExpiryUnits: 0,
        minimumDaysOfCover: 2,
        primaryDrivers: [],
      },
    },
  ],
  flows: hasFlows
    ? [{
        lineId: `line-${runId}`,
        sourceId: 'WH_01',
        destinationId: 'DEST_001',
        skuId: 'SKU_001',
        quantity: 25,
        freightCost: 7.5,
        verificationStatus: 'verified',
      }]
    : [],
})

describe('Distribution network map panel', () => {
  it('renders valid markers and synchronizes a selected shipment with the plan detail', async () => {
    getRunNetwork.mockResolvedValue(makeNetwork('run-selected'))
    const onSelectLine = vi.fn()
    render(
      <NetworkMapPanel
        runId="run-selected"
        selectedLineId={null}
        onSelectLine={onSelectLine}
      />
    )

    expect(await screen.findByText('North Warehouse')).toBeTruthy()
    const warehouseMarker = screen.getByRole('button', { name: 'Map marker 40.7,-74' })
    expect(warehouseMarker).toBeTruthy()
    fireEvent.click(warehouseMarker)
    expect(screen.getAllByText(/100 units/).length).toBeGreaterThan(0)
    fireEvent.click(screen.getByRole('button', { name: 'line-run-selected' }))
    expect(onSelectLine).toHaveBeenCalledWith('line-run-selected')
    expect(screen.getAllByText('SKU_001').length).toBeGreaterThan(0)
    expect(screen.getAllByText('7.5').length).toBeGreaterThan(0)
  })

  it('keeps unlocated locations accessible and shows the empty-plan state', async () => {
    getRunNetwork.mockResolvedValue(makeNetwork('run-empty', false, false))
    render(<NetworkMapPanel runId="run-empty" selectedLineId={null} />)

    expect(await screen.findByText('No locations have valid coordinates')).toBeTruthy()
    expect(screen.getAllByText('No coordinates')).toHaveLength(2)
    expect(screen.getByText('This selected optimization run contains no shipment lines.')).toBeTruthy()
    expect(screen.getByText('Optional coordinate mapping')).toBeTruthy()
  })

  it('refreshes the visible flows when the selected run changes', async () => {
    getRunNetwork
      .mockResolvedValueOnce(makeNetwork('run-one'))
      .mockResolvedValueOnce(makeNetwork('run-two'))
    const { rerender } = render(
      <NetworkMapPanel runId="run-one" selectedLineId={null} />
    )
    expect(await screen.findByRole('button', { name: 'line-run-one' })).toBeTruthy()

    rerender(<NetworkMapPanel runId="run-two" selectedLineId={null} />)
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'line-run-two' })).toBeTruthy()
      expect(screen.queryByRole('button', { name: 'line-run-one' })).toBeNull()
    })
  })

  it('shows API failures without rendering fabricated locations or flows', async () => {
    getRunNetwork.mockRejectedValue(new Error('Network offline'))
    render(<NetworkMapPanel runId="run-error" selectedLineId={null} />)

    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('Network offline')
    expect(screen.queryByText('North Warehouse')).toBeNull()
    expect(screen.queryByText('Selected run allocation flows')).toBeNull()
  })
})
