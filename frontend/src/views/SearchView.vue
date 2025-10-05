<!-- views/SearchView.vue -->
<template>
  <div class="search-container">
    <h2 class="page-title">搜索小说</h2>

    <el-card>
      <div class="search-form">
        <el-input
          v-model="searchQuery"
          placeholder="输入小说名称或作者进行搜索"
          class="search-input"
          clearable
          :prefix-icon="Search"
          @keyup.enter="handleSearch"
        />
        <el-button type="primary" @click="handleSearch" :loading="searching">搜索</el-button>
      </div>

      <div class="search-tips" v-if="!hasSearched">
        <el-empty description="输入关键词开始搜索">
          <template #description>
            <p>您可以搜索小说名称或作者，找到您想要的小说</p>
            <p>搜索到小说后，可以点击"添加"按钮将其添加到您的书库</p>
          </template>
        </el-empty>
      </div>

      <div class="search-results" v-else>
        <div v-if="novelStore.isLoading" class="search-loading">
          <el-skeleton :rows="3" animated />
          <el-skeleton :rows="3" animated />
          <el-skeleton :rows="3" animated />
        </div>

        <div v-else-if="novelStore.searchResults.length === 0" class="no-results">
          <el-empty description="暂无搜索结果">
            <template #description>
              <p>找不到与"{{ lastSearchQuery }}"相关的小说</p>
              <p>请尝试其他关键词，或检查拼写是否正确</p>
            </template>
          </el-empty>
        </div>

        <div v-else>
          <h3>搜索结果：{{ novelStore.searchResults.length }} 个结果</h3>

          <!-- 卡片布局显示搜索结果 -->
          <div class="results-grid">
            <el-card 
              v-for="novel in novelStore.searchResults" 
              :key="novel.id" 
              class="novel-card"
              shadow="hover"
            >
              <div class="novel-content">
                <!-- 封面图片 -->
                <div class="novel-cover">
                  <el-image
                    v-if="novel.cover"
                    :src="novel.cover"
                    fit="cover"
                    class="cover-image"
                    lazy
                  >
                    <template #error>
                      <div class="cover-placeholder">
                        <el-icon :size="40"><Picture /></el-icon>
                      </div>
                    </template>
                  </el-image>
                  <div v-else class="cover-placeholder">
                    <el-icon :size="40"><Picture /></el-icon>
                  </div>
                </div>

                <!-- 小说信息 -->
                <div class="novel-info">
                  <div class="novel-header">
                    <h3 class="novel-title">{{ novel.title }}</h3>
                    <!-- 评分标签隐藏，因为番茄API返回的搜索结果评分都是8.5 -->
                    <!-- <el-tag v-if="novel.score" type="warning" size="small">
                      <el-icon><Star /></el-icon>
                      {{ novel.score }}分
                    </el-tag> -->
                  </div>

                  <div class="novel-meta">
                    <span class="meta-item">
                      <el-icon><User /></el-icon>
                      {{ novel.author || '未知' }}
                    </span>
                    <span v-if="novel.category" class="meta-item">
                      <el-icon><FolderOpened /></el-icon>
                      {{ novel.category }}
                    </span>
                  </div>

                  <div v-if="novel.description" class="novel-description">
                    <el-text line-clamp="3" :title="novel.description">
                      {{ novel.description }}
                    </el-text>
                  </div>

                  <div class="novel-actions">
                    <el-button
                      type="primary"
                      size="default"
                      @click="addNovel(novel.id, false)"
                      :loading="addingNovelId === novel.id && !isPreviewMode"
                      :disabled="addingNovelId === novel.id"
                    >
                      <el-icon><Download /></el-icon>
                      下载全本
                    </el-button>
                    <el-button
                      type="success"
                      size="default"
                      @click="addNovel(novel.id, true)"
                      :loading="addingNovelId === novel.id && isPreviewMode"
                      :disabled="addingNovelId === novel.id"
                    >
                      <el-icon><View /></el-icon>
                      前十章预览
                    </el-button>
                  </div>
                </div>
              </div>
            </el-card>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { 
  Search, 
  Picture, 
  Star, 
  User, 
  FolderOpened, 
  Download, 
  View 
} from '@element-plus/icons-vue'
import { useNovelStore, useAuthStore } from '../store'
import api from '../api'
import type { NovelSearchResult } from '../api'

const novelStore = useNovelStore()
const authStore = useAuthStore()

// 页面状态
const searchQuery = ref('')
const lastSearchQuery = ref('')
const hasSearched = ref(false)
const searching = ref(false)
const addingNovelId = ref<string | null>(null)
const isPreviewMode = ref(false) // 记录当前操作是否为预览模式
const socketConnected = computed(() => api.WebSocketAPI.isConnected())

// 处理搜索
const handleSearch = async () => {
  if (!searchQuery.value.trim()) {
    ElMessage.warning('请输入搜索关键词')
    return
  }

  searching.value = true
  lastSearchQuery.value = searchQuery.value

  try {
    await novelStore.searchNovels(searchQuery.value)
    hasSearched.value = true
  } finally {
    searching.value = false
  }
}

// 添加小说
const addNovel = async (novelId: string, isPreview: boolean) => {
  addingNovelId.value = novelId
  isPreviewMode.value = isPreview

  try {
    // 如果是预览模式，传入 max_chapters = 10
    const maxChapters = isPreview ? 10 : undefined
    const response = await novelStore.addNovel(novelId, maxChapters)

    if (response) {
      const successMsg = isPreview
        ? '小说添加成功，开始下载前10章（预览模式）'
        : '小说添加成功，开始下载全本'
      ElMessage.success(successMsg)
    }
  } catch (err) {
    ElMessage.error('添加小说失败')
  } finally {
    addingNovelId.value = null
    isPreviewMode.value = false
  }
}
</script>

<style scoped>
.search-container {
  padding-bottom: 20px;
}

.page-title {
  margin-bottom: 20px;
}

.search-form {
  display: flex;
  margin-bottom: 20px;
  gap: 10px;
}

.search-input {
  flex: 1;
}

.search-tips {
  margin: 40px 0;
}

.no-results {
  margin: 40px 0;
}

.search-loading {
  padding: 20px 0;
}

/* 卡片网格布局 */
.results-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: 20px;
  margin-top: 20px;
}

.novel-card {
  height: 100%;
  transition: transform 0.2s;
}

.novel-card:hover {
  transform: translateY(-4px);
}

.novel-content {
  display: flex;
  gap: 16px;
  height: 100%;
}

/* 封面图片 */
.novel-cover {
  flex-shrink: 0;
  width: 120px;
  height: 160px;
  border-radius: 4px;
  overflow: hidden;
  background: #f5f7fa;
}

.cover-image {
  width: 100%;
  height: 100%;
}

.cover-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

/* 小说信息 */
.novel-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0; /* 防止内容溢出 */
}

.novel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.novel-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  line-height: 1.4;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

/* 元数据信息 */
.novel-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 13px;
  color: #606266;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.meta-item .el-icon {
  font-size: 14px;
}

/* 简介 */
.novel-description {
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
  flex: 1;
  overflow: hidden;
}

/* 操作按钮 */
.novel-actions {
  display: flex;
  gap: 8px;
  margin-top: auto;
}

.novel-actions .el-button {
  flex: 1;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .results-grid {
    grid-template-columns: 1fr;
  }
  
  .novel-content {
    flex-direction: column;
  }
  
  .novel-cover {
    width: 100%;
    height: 200px;
  }
}
</style>
