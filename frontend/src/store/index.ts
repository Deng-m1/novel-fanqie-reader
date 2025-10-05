// store/index.ts
import { defineStore } from 'pinia'
import api from '../api'
import type {
  UserProfile,
  NovelSummary,
  NovelDetails,
  ChapterDetails,
  CeleryTaskStatusResponse,
  DownloadTask,
  TaskListResponse,
  LoginResponse,
  MessageResponse,
  ErrorResponse,
  PaginatedResponse,
} from '../api'

// Authentication store
export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as UserProfile | null,
    isAuthenticated: false,
    isLoading: false,
    error: null as string | null,
  }),

  actions: {
    async login(username: string, password: string): Promise<boolean> {
      this.isLoading = true
      this.error = null

      try {
        const response = await api.Auth.login({ username, password })

        if ('error' in response) {
          this.error = response.error
          return false
        }

        // Store token
        localStorage.setItem('accessToken', response.access_token)

        // Get user info
        await this.fetchUser()
        return true
      } catch (err) {
        this.error = '登录失败，请重试'
        return false
      } finally {
        this.isLoading = false
      }
    },

    async register(username: string, password: string): Promise<boolean> {
      this.isLoading = true
      this.error = null

      try {
        const response = await api.Auth.register({ username, password })

        if ('error' in response) {
          this.error = response.error
          return false
        }

        return true
      } catch (err) {
        this.error = '注册失败，请重试'
        return false
      } finally {
        this.isLoading = false
      }
    },

    async fetchUser(): Promise<void> {
      this.isLoading = true

      try {
        const response = await api.Auth.me()

        if ('error' in response) {
          this.error = response.error
          this.isAuthenticated = false
          this.user = null
          return
        }

        this.user = response
        this.isAuthenticated = true
      } catch (err) {
        this.user = null
        this.isAuthenticated = false
      } finally {
        this.isLoading = false
      }
    },

    logout(): void {
      localStorage.removeItem('accessToken')
      this.user = null
      this.isAuthenticated = false
    },

    checkAuth(): void {
      const token = localStorage.getItem('accessToken')
      if (token) {
        this.fetchUser()
      }
    },
  },
})

// Novel store
export const useNovelStore = defineStore('novel', {
  state: () => ({
    novels: [] as NovelSummary[],
    currentNovel: null as NovelDetails | null,
    currentChapter: null as ChapterDetails | null,
    pagination: {
      total: 0,
      page: 1,
      pages: 1,
      perPage: 10,
    },
    searchResults: [] as NovelSummary[],
    isLoading: false,
    error: null as string | null,
    taskId: null as string | null,
    taskStatus: null as CeleryTaskStatusResponse | null,
  }),

  actions: {
    async fetchNovels(page: number = 1, perPage: number = 10): Promise<void> {
      this.isLoading = true
      this.error = null

      try {
        const response = await api.Novels.list(page, perPage)

        if ('error' in response) {
          this.error = response.error
          return
        }

        this.novels = response.items
        this.pagination = {
          total: response.total,
          page: response.page,
          pages: response.pages,
          perPage: response.per_page,
        }
      } catch (err) {
        this.error = '获取小说列表失败'
      } finally {
        this.isLoading = false
      }
    },

    async searchNovels(query: string): Promise<void> {
      this.isLoading = true
      this.error = null

      try {
        const response = await api.Novels.search(query)

        if ('error' in response) {
          this.error = response.error
          this.searchResults = []
          return
        }

        this.searchResults = response.results
      } catch (err) {
        this.error = '搜索失败'
        this.searchResults = []
      } finally {
        this.isLoading = false
      }
    },

    async fetchNovelDetails(novelId: string): Promise<NovelDetails | null> {
      this.isLoading = true
      this.error = null

      try {
        const response = await api.Novels.details(novelId)

        if ('error' in response) {
          this.error = response.error
          return null
        }

        this.currentNovel = response
        return response
      } catch (err) {
        this.error = '获取小说详情失败'
        return null
      } finally {
        this.isLoading = false
      }
    },

    async fetchChapterContent(novelId: string, chapterId: string): Promise<void> {
      this.isLoading = true
      this.error = null

      try {
        const response = await api.Novels.getChapterContent(novelId, chapterId)

        if ('error' in response) {
          this.error = response.error
          return
        }

        this.currentChapter = response
      } catch (err) {
        this.error = '获取章节内容失败'
      } finally {
        this.isLoading = false
      }
    },

    async addNovel(novelId: string, maxChapters?: number): Promise<{ task_id: string } | null> {
      this.isLoading = true
      this.error = null

      try {
        const requestData: { novel_id: string; max_chapters?: number } = { novel_id: novelId }
        if (maxChapters !== undefined) {
          requestData.max_chapters = maxChapters
        }
        
        const response = await api.Novels.add(requestData)

        if ('error' in response) {
          this.error = response.error
          return null
        }

        this.taskId = response.celery_task_id || null
        return { task_id: this.taskId || '' }
      } catch (err) {
        this.error = '添加小说失败'
        return null
      } finally {
        this.isLoading = false
      }
    },

    async checkTaskStatus(taskId: string): Promise<CeleryTaskStatusResponse | null> {
      try {
        const response = await api.Tasks.getStatus(taskId)

        if ('error' in response) {
          this.error = response.error
          return null
        }

        this.taskStatus = response
        return response
      } catch (err) {
        this.error = '获取任务状态失败'
        return null
      }
    },

    resetSearch(): void {
      this.searchResults = []
    },
  },
})

// Task store - New store for task management
export const useTaskStore = defineStore('task', {
  state: () => ({
    tasks: [] as DownloadTask[],
    isLoading: false,
    error: null as string | null,
  }),

  actions: {
    async fetchTasks(): Promise<void> {
      this.isLoading = true
      this.error = null

      try {
        const response = await api.Tasks.list()

        if ('error' in response) {
          this.error = response.error
          return
        }

        this.tasks = response.tasks
      } catch (err) {
        this.error = '获取任务列表失败'
      } finally {
        this.isLoading = false
      }
    },

    async terminateTask(taskId: number): Promise<DownloadTask | null> {
      this.isLoading = true
      this.error = null

      try {
        const response = await api.Tasks.terminate(taskId)

        if ('error' in response) {
          this.error = response.error
          return null
        }

        // Update task in list
        const index = this.tasks.findIndex((t) => t.id === taskId)
        if (index !== -1) {
          this.tasks[index] = response.task
        }

        return response.task
      } catch (err) {
        this.error = '终止任务失败'
        return null
      } finally {
        this.isLoading = false
      }
    },

    async deleteTask(taskId: number): Promise<boolean> {
      this.isLoading = true
      this.error = null

      try {
        const response = await api.Tasks.delete(taskId)

        if ('error' in response) {
          this.error = response.error
          return false
        }

        // Remove task from list
        this.tasks = this.tasks.filter((t) => t.id !== taskId)
        return true
      } catch (err) {
        this.error = '删除任务失败'
        return false
      } finally {
        this.isLoading = false
      }
    },

    async redownloadTask(taskId: number): Promise<DownloadTask | null> {
      this.isLoading = true
      this.error = null

      try {
        const response = await api.Tasks.redownload(taskId)

        if ('error' in response) {
          this.error = response.error
          return null
        }

        // Update task in list
        const index = this.tasks.findIndex((t) => t.id === taskId)
        if (index !== -1) {
          this.tasks[index] = response.task
        }

        return response.task
      } catch (err) {
        this.error = '重新下载任务失败'
        return null
      } finally {
        this.isLoading = false
      }
    },

    updateTaskFromWebSocket(taskData: DownloadTask): void {
      const index = this.tasks.findIndex((t) => t.id === taskData.id)
      if (index !== -1) {
        this.tasks[index] = taskData
      } else {
        this.tasks.push(taskData)
      }
    },

    setupWebSocketListener(): void {
      const token = localStorage.getItem('accessToken')
      if (!token) return

      // Connect to WebSocket
      api.WebSocketAPI.connect(token)
        .then(() => {
          // Register task update handler
          api.WebSocketAPI.onTaskUpdate(this.updateTaskFromWebSocket)
        })
        .catch((err) => {
          console.error('WebSocket connection failed:', err)
        })
    },
  },
})

// Stats store
export const useStatsStore = defineStore('stats', {
  state: () => ({
    uploadStats: [] as { date: string; count: number }[],
    genreStats: [] as { name: string; value: number }[],
    isLoading: false,
    error: null as string | null,
  }),

  actions: {
    async fetchUploadStats(): Promise<void> {
      this.isLoading = true
      this.error = null

      try {
        const response = await api.Stats.getUploadStats()

        if ('error' in response) {
          this.error = response.error
          return
        }

        this.uploadStats = response
      } catch (err) {
        this.error = '获取上传统计数据失败'
      } finally {
        this.isLoading = false
      }
    },

    async fetchGenreStats(): Promise<void> {
      this.isLoading = true
      this.error = null

      try {
        const response = await api.Stats.getGenreStats()

        if ('error' in response) {
          this.error = response.error
          return
        }

        this.genreStats = response
      } catch (err) {
        this.error = '获取类型统计数据失败'
      } finally {
        this.isLoading = false
      }
    },
  },
})
