<!-- views/HomeView.vue -->
<template>
  <div class="home-container">
    <el-container>
      <el-header class="main-header">
        <div class="logo">
          <h1>小说管理系统</h1>
        </div>
        <div class="user-info">
          <span class="internal-mode-badge">内部API模式</span>
        </div>
      </el-header>

      <el-container>
        <el-aside width="200px" class="main-aside">
          <el-menu :default-active="activeMenu" class="main-menu" router>
            <el-menu-item index="/">
              <el-icon><data-analysis /></el-icon>
              <span>数据大屏</span>
            </el-menu-item>
            <el-menu-item index="/novels">
              <el-icon><reading /></el-icon>
              <span>小说列表</span>
            </el-menu-item>
            <el-menu-item index="/search">
              <el-icon><search /></el-icon>
              <span>搜索小说</span>
            </el-menu-item>
            <el-menu-item index="/upload">
              <el-icon><upload /></el-icon>
              <span>添加小说</span>
            </el-menu-item>
            <el-menu-item index="/tasks">
              <el-icon><document /></el-icon>
              <span>任务管理</span>
            </el-menu-item>
          </el-menu>
        </el-aside>

        <el-main class="main-content">
          <router-view />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown, DataAnalysis, Reading, Search, Upload, Document } from '@element-plus/icons-vue'
import { useAuthStore, useTaskStore } from '../store'
import api from '../api'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const taskStore = useTaskStore()

const activeMenu = computed(() => route.path)

// Internal API mode - no authentication required
// Authentication and WebSocket connection code removed
// All API calls will work without tokens

onMounted(() => {
  // In internal API mode, no authentication check needed
  console.log('Running in internal API mode - no authentication')
})
</script>

<style scoped>
.home-container {
  height: 100vh;
  overflow: hidden;
}

.main-header {
  background-color: #409eff;
  color: white;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  height: 60px;
}

.main-aside {
  background-color: #f5f7fa;
  height: calc(100vh - 60px);
  border-right: 1px solid #e6e6e6;
}

.main-menu {
  height: 100%;
  border-right: none;
}

.main-content {
  padding: 20px;
  height: calc(100vh - 60px);
  overflow-y: auto;
}

.user-dropdown {
  cursor: pointer;
  display: flex;
  align-items: center;
  color: white;
  font-size: 14px;
}

.user-dropdown .el-icon {
  margin-left: 5px;
}

.internal-mode-badge {
  background-color: rgba(255, 255, 255, 0.2);
  color: white;
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 500;
}
</style>
