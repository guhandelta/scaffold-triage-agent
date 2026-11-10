import { client } from '@/client/client.gen'

// Tests call the API through the generated client, so give it an absolute base URL.
client.setConfig({ baseUrl: 'http://localhost' })
