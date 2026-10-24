import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import React from 'react'
import { DataTable } from '@/components/shared/DataTable'

describe('DataTable sorting, clicking, and footer', () => {
  const columns = [
    { key: 'id', header: 'ID', sortable: true },
    { key: 'name', header: 'Product Name', sortable: true },
    { key: 'qty', header: 'Quantity', sortable: true, align: 'right' },
  ]

  const mockData = [
    { id: 'item-2', name: 'Beta Formulation', qty: 200 },
    { id: 'item-1', name: 'Alpha Vaccine', qty: 500 },
    { id: 'item-3', name: 'Gamma Injectable', qty: 100 },
  ]

  it('renders table headers and data rows', () => {
    render(<DataTable columns={columns} data={mockData} rowKey="id" />)
    expect(screen.getByText('Product Name')).toBeDefined()
    expect(screen.getByText('Alpha Vaccine')).toBeDefined()
    expect(screen.getByText('Beta Formulation')).toBeDefined()
    expect(screen.getByText('Gamma Injectable')).toBeDefined()
  })

  it('sorts records when clicking sortable header column', () => {
    render(<DataTable columns={columns} data={mockData} rowKey="id" />)
    const nameHeader = screen.getByText('Product Name')

    // Click to sort ascending by name
    fireEvent.click(nameHeader)
    const rowsAsc = screen.getAllByRole('row')
    expect(rowsAsc[1].textContent).toContain('Alpha Vaccine')

    // Click again to sort descending by name
    fireEvent.click(nameHeader)
    const rowsDesc = screen.getAllByRole('row')
    expect(rowsDesc[1].textContent).toContain('Gamma Injectable')
  })

  it('handles row click callbacks', () => {
    const handleRowClick = vi.fn()
    render(<DataTable columns={columns} data={mockData} onRowClick={handleRowClick} rowKey="id" />)

    const firstRow = screen.getByText('Beta Formulation').closest('tr')
    fireEvent.click(firstRow)
    expect(handleRowClick).toHaveBeenCalledTimes(1)
    expect(handleRowClick).toHaveBeenCalledWith(mockData[0])
  })

  it('renders custom table footer when provided', () => {
    const customFooter = (
      <tr>
        <td colSpan={2}>Total Quantity</td>
        <td>800 units</td>
      </tr>
    )
    render(<DataTable columns={columns} data={mockData} footer={customFooter} rowKey="id" />)
    expect(screen.getByText('Total Quantity')).toBeDefined()
    expect(screen.getByText('800 units')).toBeDefined()
  })
})
