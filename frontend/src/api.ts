import axios, {
  type AxiosInstance,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios'
import { io, Socket } from 'socket.io-client'

// --- General API Response Types ---

export interface ErrorResponse {
  error: string
  msg?: string // Sometimes 'msg' is used instead of 'error'
}

export interface MessageResponse {
  msg: string
  message?: string // Sometimes 'message' is used
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  pages: number
  per_page: number
}

// --- Auth Types ---

export interface RegisterCredentials {
  username: string
  password?: string // Password might not be needed in response/profile
}

export interface LoginCredentials {
  username: string
  password?: string
}

export interface LoginResponse {
  access_token: string
}

export interface UserProfile {
  id: number // User ID is integer in backend model
  username: string
}

// --- Novel Types ---
export interface NovelSearchResult {
  id: string // Backend search returns string ID
  title: string
  author: string
  cover: string | null // 封面图片URL
  description: string | null // 小说简介
  category: string | null // 分类标签
  score: string | null // 评分
}

export interface NovelSearchResponse {
  results: NovelSearchResult[]
}

export interface AddNovelRequest {
  novel_id: string // Input expects string
  max_chapters?: number // Optional: limit chapters to download (e.g. 10 for preview)
}

// Matches DownloadTask.to_dict() structure in backend
export interface AddNovelResponse {
  id: number
  user_id: number
  novel_id: string // Matches string in backend dict
  novel: {
    id: string // Matches string in backend dict
    title: string
    author: string | null
  } | null
  celery_task_id: string | null
  status: string // Enum name as string
  progress: number
  message: string | null
  created_at: string | null // ISO format string
  updated_at: string | null // ISO format string
}

export interface NovelSummary {
  id: string // String in list response
  title: string
  author: string | null
  status: string | null
  tags: string | null
  total_chapters: number | null // Chapters from source
  last_crawled_at: string | null // ISO format string
  created_at: string | null // ISO format string
  cover_image_url: string | null
}

export interface NovelDetails {
  id: string // String in detail response
  title: string
  author: string | null
  description: string | null
  status: string | null
  tags: string | null
  total_chapters_source: number | null // Chapters reported by source
  chapters_in_db: number // Chapters actually in DB
  last_crawled_at: string | null // ISO format string
  created_at: string | null // ISO format string
  cover_image_url: string | null
}

export interface ChapterSummary {
  id: string // String in list response
  index: number
  title: string
  fetched_at: string | null // ISO format string
}

export interface ChapterDetails {
  id: string // String in detail response
  novel_id: string // String in detail response
  index: number
  title: string
  content: string
}

// --- Task Types ---

// Corresponds to TaskStatus enum in backend
export enum TaskStatusEnum {
  PENDING = 'PENDING',
  DOWNLOADING = 'DOWNLOADING',
  PROCESSING = 'PROCESSING',
  COMPLETED = 'COMPLETED',
  FAILED = 'FAILED',
  TERMINATED = 'TERMINATED',
}

// Corresponds to DownloadTask.to_dict() in backend models.py
export interface DownloadTask {
  id: number
  user_id: number
  novel_id: string
  novel: {
    id: string
    title: string
    author: string | null
  } | null
  celery_task_id: string | null
  status: TaskStatusEnum // Use string enum for status
  progress: number
  message: string | null
  created_at: string | null // ISO format string
  updated_at: string | null // ISO format string
  deleted?: boolean // Added for frontend state management on delete
}

export interface TaskListResponse {
  tasks: DownloadTask[]
}

// Celery task status structure from /api/tasks/status/<task_id>
export interface CeleryTaskStatusMeta {
  // Based on process_novel_task return structure
  status?: string // SUCCESS, FAILURE, TERMINATED etc. from the task itself
  message?: string
  chapters_processed_db?: number
  errors?: number
  // OR Error details if task failed at celery level
  exc_type?: string
  exc_message?: string
  // Or any other structure the task might return/set in meta
  [key: string]: unknown // Allow other properties
}

export interface CeleryTaskStatusResponse {
  task_id: string
  status: string // PENDING, STARTED, SUCCESS, FAILURE, REVOKED etc. (Celery states)
  result: string | null // User-friendly status description from backend
  meta: CeleryTaskStatusMeta | null // Specific task result/error details
  traceback?: string // Optional traceback on failure
}

// --- Stats Types ---
export interface UploadStat {
  date: string // Date string YYYY-MM-DD
  count: number
}

export interface GenreStat {
  name: string // Genre name
  value: number // Count
}

// --- Axios Instance Setup (HTTP API) ---
const apiClient: AxiosInstance = axios.create({
  baseURL: '/api', // Base URL is /api
})

// --- JWT Interceptor (HTTP API) - DISABLED for internal API mode ---
// No authentication token needed for internal API
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig): InternalAxiosRequestConfig => {
    // Internal API mode - no token required, skip all authentication
    return config
  },
  (error) => Promise.reject(error),
)

// --- Response Data Helper (HTTP API) ---
const responseBody = <T>(response: AxiosResponse<T>): T => response.data

// --- Generic API Request Functions (HTTP API) ---
const requests = {
  get: <T>(url: string, params?: URLSearchParams) =>
    apiClient.get<T>(url, { params }).then(responseBody),
  post: <T>(url: string, body: unknown) => apiClient.post<T>(url, body).then(responseBody),
  delete: <T>(url: string) => apiClient.delete<T>(url).then(responseBody),
}

// --- HTTP API Function Collections ---

const Auth = {
  register: (credentials: RegisterCredentials): Promise<MessageResponse | ErrorResponse> =>
    requests.post<MessageResponse | ErrorResponse>('/auth/register', credentials),
  login: (credentials: LoginCredentials): Promise<LoginResponse | ErrorResponse> =>
    requests.post<LoginResponse | ErrorResponse>('/auth/login', credentials),
  me: (): Promise<UserProfile | ErrorResponse> =>
    requests.get<UserProfile | ErrorResponse>('/auth/me'),
}

const Novels = {
  search: (query: string): Promise<NovelSearchResponse | ErrorResponse> => {
    const params = new URLSearchParams({ query })
    return requests.get<NovelSearchResponse | ErrorResponse>('/search', params)
  },
  add: (data: AddNovelRequest): Promise<AddNovelResponse | ErrorResponse> =>
    requests.post<AddNovelResponse | ErrorResponse>('/novels', data),

  list: (
    page: number = 1,
    perPage: number = 10,
  ): Promise<PaginatedResponse<NovelSummary> | ErrorResponse> => {
    const params = new URLSearchParams({
      page: page.toString(),
      per_page: perPage.toString(),
    })
    type RawNovelListResponse =
      | {
          novels: NovelSummary[]
          total: number
          page: number
          pages: number
          per_page: number
        }
      | ErrorResponse

    return apiClient.get<RawNovelListResponse>('/novels', { params }).then((res) => {
      if (typeof res.data === 'object' && res.data && 'error' in res.data) {
        return res.data as ErrorResponse
      }
      const data = res.data as Exclude<RawNovelListResponse, ErrorResponse>
      return {
        items: data.novels,
        total: data.total,
        page: data.page,
        pages: data.pages,
        per_page: data.per_page,
      }
    })
  },

  details: (novelId: string): Promise<NovelDetails | ErrorResponse> =>
    requests.get<NovelDetails | ErrorResponse>(`/novels/${novelId}`),

  listChapters: (
    novelId: string,
    page: number = 1,
    perPage: number = 50,
  ): Promise<(PaginatedResponse<ChapterSummary> & { novel_id: string }) | ErrorResponse> => {
    const params = new URLSearchParams({
      page: page.toString(),
      per_page: perPage.toString(),
    })
    type RawChapterListResponse =
      | {
          chapters: ChapterSummary[]
          total: number
          page: number
          pages: number
          per_page: number
          novel_id: string
        }
      | ErrorResponse

    return apiClient
      .get<RawChapterListResponse>(`/novels/${novelId}/chapters`, { params })
      .then((res) => {
        if (typeof res.data === 'object' && res.data && 'error' in res.data) {
          return res.data as ErrorResponse
        }
        const data = res.data as Exclude<RawChapterListResponse, ErrorResponse>
        return {
          items: data.chapters,
          total: data.total,
          page: data.page,
          pages: data.pages,
          per_page: data.per_page,
          novel_id: data.novel_id,
        }
      })
  },

  getChapterContent: (
    novelId: string,
    chapterId: string,
  ): Promise<ChapterDetails | ErrorResponse> =>
    requests.get<ChapterDetails | ErrorResponse>(`/novels/${novelId}/chapters/${chapterId}`),

  getCoverUrl: (novelId: string): string => `/api/novels/${novelId}/cover`,

  fetchCoverBlob: (novelId: string): Promise<string | ErrorResponse> => {
    const path = `/novels/${novelId}/cover`
    return apiClient
      .get<Blob>(path, { responseType: 'blob' })
      .then((res) => {
        if (res.data.type.startsWith('image/')) {
          return URL.createObjectURL(res.data)
        } else if (res.data.type === 'application/json') {
          return res.data.text().then((text) => {
            try {
              return JSON.parse(text) as ErrorResponse
            } catch (e) {
              return { error: 'Failed to parse error response for cover' } as ErrorResponse
            }
          })
        } else {
          return { error: 'Unexpected response type for cover image' } as ErrorResponse
        }
      })
      .catch((error) => {
        if (
          error.response &&
          error.response.data instanceof Blob &&
          error.response.data.type === 'application/json'
        ) {
          return error.response.data.text().then((text: string) => {
            try {
              return JSON.parse(text) as ErrorResponse
            } catch (e) {
              return { error: 'Failed to parse error blob for cover' } as ErrorResponse
            }
          })
        }
        return { error: error.message || 'Failed to fetch cover blob' } as ErrorResponse
      })
  },

  getDownloadUrl: (novelId: string): string => `/api/novels/${novelId}/download`,

  fetchNovelBlob: (novelId: string): Promise<Blob | ErrorResponse> => {
    const path = `/novels/${novelId}/download`
    return apiClient
      .get<Blob>(path, { responseType: 'blob' })
      .then((res) => res.data)
      .catch((error) => {
        if (
          error.response &&
          error.response.data instanceof Blob &&
          error.response.data.type === 'application/json'
        ) {
          return error.response.data.text().then((text: string) => {
            try {
              return JSON.parse(text) as ErrorResponse
            } catch (e) {
              return { error: 'Failed to parse error response from blob' } as ErrorResponse
            }
          })
        }
        return { error: error.message || 'Failed to download novel file' } as ErrorResponse
      })
  },
}

const Tasks = {
  getStatus: (taskId: string): Promise<CeleryTaskStatusResponse | ErrorResponse> =>
    requests.get<CeleryTaskStatusResponse | ErrorResponse>(`/tasks/status/${taskId}`),
  list: (): Promise<TaskListResponse | ErrorResponse> =>
    requests.get<TaskListResponse | ErrorResponse>('/tasks/list'),
  terminate: (
    dbTaskId: number,
  ): Promise<(MessageResponse & { task: DownloadTask }) | ErrorResponse> =>
    requests.post<(MessageResponse & { task: DownloadTask }) | ErrorResponse>(
      `/tasks/${dbTaskId}/terminate`,
      {},
    ),
  delete: (dbTaskId: number): Promise<MessageResponse | ErrorResponse> =>
    requests.delete<MessageResponse | ErrorResponse>(`/tasks/${dbTaskId}`),
  redownload: (
    dbTaskId: number,
  ): Promise<(MessageResponse & { task: DownloadTask }) | ErrorResponse> =>
    requests.post<(MessageResponse & { task: DownloadTask }) | ErrorResponse>(
      `/tasks/${dbTaskId}/redownload`,
      {},
    ),
}

const Stats = {
  getUploadStats: (): Promise<UploadStat[] | ErrorResponse> =>
    requests.get<UploadStat[] | ErrorResponse>('/stats/upload'),
  getGenreStats: (): Promise<GenreStat[] | ErrorResponse> =>
    requests.get<GenreStat[] | ErrorResponse>('/stats/genre'),
  getWordCloudUrl: (novelId: string): string => `/api/stats/wordcloud/${novelId}`,
  fetchWordCloudBlob: (novelId: string): Promise<string | ErrorResponse> => {
    const path = `/stats/wordcloud/${novelId}`
    return apiClient
      .get<Blob>(path, { responseType: 'blob' })
      .then((res) => {
        if (res.data.type.startsWith('image/')) {
          return URL.createObjectURL(res.data)
        } else if (res.data.type === 'application/json') {
          return res.data.text().then((text) => {
            try {
              return JSON.parse(text) as ErrorResponse
            } catch (e) {
              return { error: 'Failed to parse error response for word cloud' } as ErrorResponse
            }
          })
        } else {
          return { error: 'Unexpected response type for word cloud' } as ErrorResponse
        }
      })
      .catch((error) => {
        if (
          error.response &&
          error.response.data instanceof Blob &&
          error.response.data.type === 'application/json'
        ) {
          return error.response.data.text().then((text: string) => {
            try {
              return JSON.parse(text) as ErrorResponse
            } catch (e) {
              return { error: 'Failed to parse error blob' } as ErrorResponse
            }
          })
        }
        return { error: error.message || 'Failed to fetch word cloud blob' } as ErrorResponse
      })
  },
}

// --- WebSocket API Module ---
const WebSocketAPI = (() => {
  let socket: Socket | null = null
  let taskUpdateCallback: ((taskData: DownloadTask) => void) | null = null

  // Define types for events based on backend emits/listens
  interface ServerToClientEvents {
    request_auth: (data: { message: string }) => void
    auth_response: (data: { success: boolean; message: string }) => void
    task_update: (taskData: DownloadTask) => void // Backend emits this
    // Add other events the server might emit to the client
  }

  interface ClientToServerEvents {
    authenticate: (data: { token: string }) => void // Backend listens for this
    // Add other events the client might emit to the server
  }

  function connect(token: string | null): Promise<boolean> {
    return new Promise((resolve, reject) => {
      if (socket?.connected) {
        console.log('WebSocket already connected.')
        resolve(true)
        return
      }

      // Disconnect previous socket if exists but not connected
      if (socket) {
        socket.disconnect()
        socket = null
      }

      // --- CONFIGURATION NEEDED ---
      // Adjust the URL and path based on your server deployment
      // If served from the same origin as the frontend:
      const socketUrl = undefined // Let Socket.IO client determine default URL
      const socketPath = '/socket.io' // Default path for Flask-SocketIO
      // If served from a different origin:
      // const socketUrl = 'ws://your-backend-domain.com';
      // const socketPath = '/socket.io'; // Or whatever path is configured
      // ---------------------------

      // Explicitly define event types for better type safety
      socket = io(socketUrl, {
        path: socketPath,
        autoConnect: false, // We call connect() manually
      }) as Socket<ServerToClientEvents, ClientToServerEvents>

      // Remove previous listeners to prevent duplicates if connect is called again
      socket.off('connect')
      socket.off('request_auth')
      socket.off('auth_response')
      socket.off('task_update')
      socket.off('connect_error')
      socket.off('disconnect')

      // Setup listeners
      socket.on('connect', () => {
        console.log('WebSocket connected, SID:', socket?.id)
        // Wait for server to request authentication
      })

      socket.on('request_auth', () => {
        console.log('WebSocket authentication requested by server.')
        if (token) {
          console.log('Sending authentication token...')
          socket?.emit('authenticate', { token })
        } else {
          console.error('WebSocket auth requested, but no token found.')
          socket?.disconnect()
          reject(new Error('No authentication token available.'))
        }
      })

      socket.on('auth_response', (data) => {
        if (data.success) {
          console.log('WebSocket authentication successful.')
          resolve(true)
        } else {
          console.error('WebSocket authentication failed:', data.message)
          socket?.disconnect()
          reject(new Error(`Authentication failed: ${data.message}`))
        }
      })

      socket.on('task_update', (taskData) => {
        // console.debug('WebSocket received task_update:', taskData);
        // Call the registered callback if it exists
        if (taskUpdateCallback) {
          try {
            taskUpdateCallback(taskData)
          } catch (e) {
            console.error('Error in taskUpdateCallback:', e)
          }
        }
      })

      socket.on('connect_error', (err) => {
        console.error('WebSocket connection error:', err.message)
        if (socket) {
          socket.disconnect() // Ensure disconnect on error
          socket = null
        }
        reject(err)
      })

      socket.on('disconnect', (reason) => {
        console.log('WebSocket disconnected:', reason)
        if (socket) {
          // Check if socket exists before nulling
          socket = null
        }
        // Optionally notify UI or attempt reconnect based on reason
      })

      // Attempt connection
      console.log('Attempting to connect WebSocket...')
      socket.connect()
    })
  }

  function disconnect(): void {
    if (socket?.connected) {
      console.log('Disconnecting WebSocket...')
      socket.disconnect()
    }
    if (socket) {
      // Also nullify if exists but not connected
      socket = null
    }
    taskUpdateCallback = null // Clear callback on disconnect
  }

  // Function for UI components to register their update handler
  function onTaskUpdate(callback: (taskData: DownloadTask) => void): void {
    taskUpdateCallback = callback
  }

  // Function to check current connection status
  function isConnected(): boolean {
    return socket?.connected ?? false
  }

  return {
    connect,
    disconnect,
    onTaskUpdate,
    isConnected,
    // Expose the socket instance if direct access is needed (use with caution)
    // getSocket: () => socket,
  }
})()

// --- Default Export ---
export default {
  Auth,
  Novels,
  Tasks,
  Stats,
  WebSocketAPI,
  apiClient,
}
