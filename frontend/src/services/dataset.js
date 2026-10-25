import { get, postForm } from './apiClient'

export async function listDatasets() {
  return get('/datasets')
}

export async function getDataset(datasetId) {
  return get(`/datasets/${datasetId}`)
}

export async function getDatasetPreview(datasetId, limit = 20) {
  return get(`/datasets/${datasetId}/preview`, { query: { limit } })
}

export async function uploadDataset(file, options = {}) {
  if (!file) {
    throw new Error('Select a CSV or Excel dataset file before uploading.')
  }

  const form = new FormData()
  form.append('file', file)
  if (options.datasetName) form.append('dataset_name', options.datasetName)
  if (options.replaceExisting) form.append('replace_existing', String(Boolean(options.replaceExisting)))

  return postForm('/datasets/upload', form)
}

export async function validateDataset(datasetId, payload = {}) {
  return postForm(`/datasets/${datasetId}/validate`, new FormData())
}

export async function activateDataset(datasetId) {
  return postForm(`/datasets/${datasetId}/activate`, new FormData())
}
