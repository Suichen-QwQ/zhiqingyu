<template>
  <div class="chat-layout">
    <!-- 左侧边栏：历史聊天记录 -->
    <div class="sidebar" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
      <div class="sidebar-header">
        <n-button
          quaternary
          circle
          size="small"
          @click="sidebarCollapsed = !sidebarCollapsed"
          class="sidebar-toggle"
        >
          <template #icon>
            <span>{{ sidebarCollapsed ? '→' : '←' }}</span>
          </template>
        </n-button>
        <n-button
          type="primary"
          @click="handleNewChat"
          class="new-chat-button"
          :disabled="loading"
        >
          <template #icon>
            <span>➕</span>
          </template>
          {{ $t('chat.newChat') }}
        </n-button>
      </div>
      <div v-if="!sidebarCollapsed" class="sidebar-content">
        <div class="sidebar-title">{{ $t('chat.chatHistory') }}</div>
        <div v-if="loadingSessions" class="sidebar-loading">
          {{ $t('chat.loadingHistory') }}
        </div>
        <div v-else-if="sessions.length === 0" class="sidebar-empty">
          {{ $t('chat.noHistory') }}
        </div>
        <div v-else class="session-list">
          <div
            v-for="session in sessions"
            :key="session.id"
            :class="['session-item', { active: session.id === sessionId }]"
            @click="handleSwitchSession(session.id)"
          >
            <div class="session-content">
              <div class="session-preview">{{ session.title || session.preview || $t('chat.newChat') }}</div>
              <div class="session-time">
                {{ formatSessionTime(session.latest_message_at || session.created_at) }}
              </div>
            </div>
            <n-button
              quaternary
              circle
              size="small"
              class="session-delete-button"
              @click.stop="handleDeleteSession(session.id)"
              :disabled="loading"
            >
              <template #icon>
                <span>🗑️</span>
              </template>
            </n-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 主聊天区域 -->
    <div class="chat-container">
      <!-- 顶部：今日主情绪 -->
      <n-card class="emotion-card" hoverable>
        <div class="emotion-card-content">
          <div class="emotion-left">
            <div class="emotion-icon-wrapper">
              <div class="emotion-icon">💭</div>
            </div>
            <span class="emotion-label">{{ $t('chat.todayEmotion') }}</span>
          </div>
          <div class="emotion-badge">
            <span class="emotion-text">
              {{ todayEmotion ? getEmotionLabel(todayEmotion) : $t('chat.noEmotion') }}
            </span>
          </div>
          <!-- 配置选择器（同一行） -->
          <div class="config-selectors-inline">
            <n-select
              v-model:value="selectedExperienceMode"
              :options="experienceModesForSelect"
              :placeholder="$t('chat.experienceMode')"
              clearable
              size="small"
              class="inline-selector"
            />
            <n-select
              v-model:value="selectedAIStyle"
              :options="aiStyles"
              :placeholder="$t('chat.aiStyle')"
              clearable
              size="small"
              class="inline-selector"
            />
            <n-select
              v-model:value="selectedChatMode"
              :options="chatModesForSelect"
              :placeholder="$t('chat.aiMode')"
              clearable
              size="small"
              class="inline-selector"
            />
          </div>
        </div>
      </n-card>

      <!-- 聊天记录区域 -->
      <div class="messages-container">
      <div v-if="messages.length === 0" class="welcome-section">
        <div class="app-logo-wrapper">
          <img src="../logo/logo.png" alt="Logo" class="welcome-icon" />
          <div class="logo-glow"></div>
        </div>
        <p class="welcome-title">{{ $t('chat.welcome') }}</p>
        <p class="welcome-desc">{{ $t('chat.welcomeDesc') }}</p>
      </div>

      <div
        v-for="(msg, index) in messages"
        :key="index"
        :class="['message-wrapper', msg.role === 'user' ? 'user-message' : 'assistant-message']"
      >
        <!-- 用户消息：普通气泡（过滤掉满意度反馈的特殊消息） -->
        <div
          v-if="msg.role === 'user' && !msg.content.startsWith('[SATISFACTION:')"
          :class="[
            'message-bubble',
            'user-bubble',
          ]"
        >
          <p class="message-content">{{ msg.content }}</p>
        </div>
        
        <!-- AI回复：如果有卡片数据则显示HeartCard，否则显示白色引导卡片 -->
        <div v-else>
          <!-- 卡片生成阶段：有card_data时显示HeartCard -->
          <div v-if="msg.card_data && hasCardData(msg.card_data)" class="assistant-card-wrapper">
            <HeartCard :card-data="msg.card_data" class="assistant-card" />
            <div class="card-action-buttons">
              <n-button
                quaternary
                size="small"
                circle
                class="card-action-button card-export-button"
                @click.stop="handleExportCard(msg.card_data)"
              >
                <template #icon>
                  <span>⇩</span>
                </template>
              </n-button>
              <n-button
                quaternary
                size="small"
                circle
                class="card-action-button card-fullscreen-toggle"
                @click.stop="openCardFullscreen(msg.card_data)"
              >
                <template #icon>
                  <span>⤢</span>
                </template>
              </n-button>
            </div>
          </div>
          <!-- 引导阶段：没有card_data时显示白色引导卡片 -->
          <div
            v-else
            class="guiding-card"
          >
            <p class="guiding-card-content">{{ msg.content }}</p>
          </div>
          
          <!-- 满意度按钮：显示在AI消息气泡下方 -->
          <div v-if="msg.should_show_satisfaction_buttons && sessionId" class="satisfaction-buttons-in-message">
            <div class="satisfaction-buttons">
              <n-button
                type="primary"
                size="large"
                :loading="loading"
                @click="handleSatisfaction(true)"
                class="satisfaction-button satisfaction-button-yes"
              >
                <template #icon>
                  <span>👍</span>
                </template>
                你说到了我的心里
              </n-button>
              <n-button
                size="large"
                :loading="loading"
                @click="handleSatisfaction(false)"
                class="satisfaction-button satisfaction-button-no"
              >
                <template #icon>
                  <span>👎</span>
                </template>
                我觉得我还需要再多跟你说一些
              </n-button>
            </div>
          </div>
        </div>
      </div>

      <div v-if="loading" class="message-wrapper assistant-message">
        <div class="message-bubble assistant-bubble loading-bubble">
          <div class="loading-dots">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <span class="loading-text">{{ $t('chat.sending') }}</span>
        </div>
      </div>

      <div ref="messagesEndRef" />
    </div>

    <!-- 输入区域 -->
    <n-card class="input-card">
      <!-- 风险级别警告 -->
      <div v-if="lastRiskLevel === 'high'" class="risk-warning">
        <n-alert type="warning" :title="$t('chat.riskWarning')" :show-icon="true">
          {{ $t('chat.riskWarningDesc') }}
        </n-alert>
      </div>
      
      <!-- 开始关心按钮 -->
      <div v-if="shouldShowCardButton && sessionId" class="card-button-wrapper">
        <n-button
          type="primary"
          size="large"
          :loading="loading"
          @click="handleGenerateCard"
          class="generate-card-button"
          block
        >
          <template #icon>
            <span>💝</span>
          </template>
          {{ $t('chat.startCaring') || '开始关心吧！' }}
        </n-button>
      </div>
      
      <div class="input-wrapper">
        <n-input
          v-model:value="input"
          type="textarea"
          :placeholder="$t('chat.inputPlaceholder')"
          :rows="3"
          :disabled="loading"
          @keydown="handleKeyPress"
          class="chat-input"
          :autosize="{ minRows: 2, maxRows: 5 }"
          :status="undefined"
        />
        <n-button
          type="primary"
          :loading="loading"
          :disabled="!input.trim()"
          @click="handleSend"
          class="send-button"
          size="large"
        >
          <template #icon>
            <span class="send-icon">✨</span>
          </template>
          {{ $t('common.send') }}
        </n-button>
      </div>
    </n-card>
    </div>
  </div>
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="cardFullscreenVisible && fullscreenCardData"
        class="card-fullscreen-overlay"
        @click.self="closeCardFullscreen"
      >
        <div class="card-fullscreen-content" @click.stop>
          <n-button quaternary circle size="large" class="card-fullscreen-close" @click="closeCardFullscreen">
            <template #icon>
              <span>✕</span>
            </template>
          </n-button>
          <n-button
            tertiary
            circle
            size="large"
            class="card-fullscreen-export"
            @click="handleExportCard(fullscreenCardData)"
          >
            <template #icon>
              <span>⇩</span>
            </template>
          </n-button>
          <HeartCard
            v-if="fullscreenCardData"
            :card-data="fullscreenCardData"
            class="heart-card-fullscreen"
          />
        </div>
      </div>
    </Transition>
  </Teleport>
  
  <!-- 模板选择对话框 - 已隐藏，供将来恢复时使用 -->
  <!--
  <n-modal
    v-model:show="templateSelectVisible"
    preset="dialog"
    title="选择导出模板"
    positive-text="导出"
    negative-text="取消"
    @positive-click="handleTemplateExport"
    @negative-click="templateSelectVisible = false"
  >
    <div class="template-select-grid">
      <div
        v-for="option in templateOptions"
        :key="option.value"
        :class="['template-option', { active: exportTemplateSelection === option.value }]"
        @click="exportTemplateSelection = option.value"
      >
        <div class="template-icon">{{ option.icon }}</div>
        <div class="template-label">{{ option.label }}</div>
      </div>
    </div>
  </n-modal>
  -->
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { NCard, NInput, NButton, NAlert, NSelect, NModal, useMessage, useDialog } from 'naive-ui'
import {
  sendChatMessage,
  getSessions,
  getSessionMessages,
  deleteSession,
  generateCard,
  type ChatMessage,
  type SessionItem,
  type CardData,
} from '@/lib/api'
import HeartCard from '@/components/HeartCard.vue'
import { generateCardHtml, type CardTemplate } from '@/lib/cardExport'

const { t } = useI18n()
const message = useMessage()
const dialog = useDialog()

const messages = ref<ChatMessage[]>([])
const input = ref('')
const loading = ref(false)
const sessionId = ref<string | null>(null)
const todayEmotion = ref<string | null>(null)
const messagesEndRef = ref<HTMLDivElement | null>(null)
const sidebarCollapsed = ref(false)
const sessions = ref<SessionItem[]>([])
const loadingSessions = ref(false)
const selectedExperienceMode = ref<'A' | 'B' | 'C' | 'D' | null>(null)
const lastRiskLevel = ref<'normal' | 'high'>('normal')
const selectedAIStyle = ref<string | null>(null)
const selectedChatMode = ref<'deep' | 'quick' | null>('deep')
const cardFullscreenVisible = ref(false)
const fullscreenCardData = ref<CardData | null>(null)
const FULLSCREEN_BODY_CLASS = 'card-fullscreen-active'
let previousBodyOverflow = ''
const templateSelectVisible = ref(false)
const currentExportCardData = ref<CardData | null>(null)
const shouldShowCardButton = ref(false)
const shouldShowSatisfactionButtons = ref(false)

// 体验模式选项（使用computed确保国际化文本正确更新）
const experienceModes = computed(() => [
  { value: 'A' as const, label: t('chat.modeA'), icon: '👂' },
  { value: 'B' as const, label: t('chat.modeB'), icon: '💡' },
  { value: 'C' as const, label: t('chat.modeC'), icon: '💪' },
  { value: 'D' as const, label: t('chat.modeD'), icon: '🌊' },
])

// 体验模式选项（用于下拉选择器）
const experienceModesForSelect = computed(() => 
  experienceModes.value.map(mode => ({
    value: mode.value,
    label: `${mode.icon} ${mode.label}`
  }))
)

// AI风格选项
const aiStyles = computed(() => [
  { value: 'comfort', label: t('chat.styleComfort') },
  { value: 'analyst', label: t('chat.styleAnalyst') },
  { value: 'coach', label: t('chat.styleCoach') },
  { value: 'mentor', label: t('chat.styleMentor') },
  { value: 'friend', label: t('chat.styleFriend') },
  { value: 'listener', label: t('chat.styleListener') },
  { value: 'growth', label: t('chat.styleGrowth') },
  { value: 'crisis_safe', label: t('chat.styleCrisisSafe') },
])

// AI模式选项
const chatModes = computed(() => [
  { value: 'deep' as const, label: t('chat.deepChatMode') },
  { value: 'quick' as const, label: t('chat.quickMode') },
])

// AI模式选项（用于下拉选择器）
const chatModesForSelect = computed(() => 
  chatModes.value.map(mode => ({
    value: mode.value,
    label: mode.label
  }))
)

const scrollToBottom = async () => {
  await nextTick()
  messagesEndRef.value?.scrollIntoView({ behavior: 'smooth' })
}

onMounted(() => {
  scrollToBottom()
  loadSessions()
})

// 加载会话列表
const loadSessions = async () => {
  const epoch = ++sessionListEpoch
  loadingSessions.value = true
  try {
    const response = await getSessions()
    if (epoch !== sessionListEpoch) return
    if (response.error) {
      console.error('Failed to load sessions:', response.error)
      return
    }
    if (response.data) {
      sessions.value = response.data.sessions
    }
  } catch (error) {
    console.error('Error loading sessions:', error)
  } finally {
    if (epoch === sessionListEpoch) loadingSessions.value = false
  }
}

// 切换会话
let viewEpoch = 0
let sessionListEpoch = 0

const handleSwitchSession = async (id: string) => {
  if (id === sessionId.value) return

  const epoch = ++viewEpoch
  loading.value = true
  try {
    const response = await getSessionMessages(id)
    if (epoch !== viewEpoch) return
    if (response.error) {
      message.error(`${t('common.error')}: ${response.error.message}`)
      return
    }
    if (response.data) {
      sessionId.value = id
      messages.value = response.data.messages
      todayEmotion.value = null // 重置情绪，因为不同会话的情绪可能不同
      lastRiskLevel.value = 'normal' // 重置风险级别
      selectedExperienceMode.value = null // 重置体验模式
      selectedAIStyle.value = null // 重置AI风格
      selectedChatMode.value = 'deep' // 重置聊天模式
      // 检查最后一条assistant消息是否应该显示按钮
      const lastAssistantMsg = [...response.data.messages].reverse().find(msg => msg.role === 'assistant')
      shouldShowCardButton.value = lastAssistantMsg?.should_show_card_button || false
      shouldShowSatisfactionButtons.value = lastAssistantMsg?.should_show_satisfaction_buttons || false
      scrollToBottom()
    }
  } catch (error) {
    if (epoch !== viewEpoch) return
    console.error('Error loading session messages:', error)
    message.error(t('chat.sendFailed'))
  } finally {
    if (epoch === viewEpoch) loading.value = false
  }
}

// 新建对话
const handleNewChat = () => {
  viewEpoch++
  loading.value = false
  sessionId.value = null
  messages.value = []
  todayEmotion.value = null
  input.value = ''
  selectedExperienceMode.value = null
  selectedAIStyle.value = null
  selectedChatMode.value = 'deep'
  lastRiskLevel.value = 'normal'
  shouldShowCardButton.value = false
  shouldShowSatisfactionButtons.value = false
}

// 删除会话
const handleDeleteSession = async (id: string) => {
  dialog.warning({
    title: t('common.confirm'),
    content: t('chat.deleteConfirm'),
    positiveText: t('common.confirm'),
    negativeText: t('common.cancel'),
    onPositiveClick: async () => {
      try {
        const response = await deleteSession(id)
        if (response.error) {
          message.error(`${t('common.error')}: ${response.error.message}`)
          return
        }

        // 如果删除的是当前会话，清空当前会话
        if (id === sessionId.value) {
          handleNewChat()
        }

        // 刷新会话列表
        await loadSessions()
        message.success(t('chat.deleteSuccess'))
      } catch (error) {
        console.error('Error deleting session:', error)
        message.error(t('chat.deleteFailed'))
      }
    },
  })
}

// 格式化会话时间
const formatSessionTime = (timeStr: string | null) => {
  if (!timeStr) return ''
  const date = new Date(timeStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))
  
  const hours = date.getHours()
  const minutes = date.getMinutes()
  const timeStr_formatted = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`
  const month = date.getMonth() + 1
  const day = date.getDate()

  if (days === 0) {
    // 今天，显示 "今天 HH:mm"
    return `今天 ${timeStr_formatted}`
  } else if (days === 1) {
    // 昨天，显示 "昨天 HH:mm"
    return `昨天 ${timeStr_formatted}`
  } else if (days < 7) {
    // 一周内，显示 "X天前 HH:mm"
    return `${days}天前 ${timeStr_formatted}`
  } else {
    // 超过7天，显示日期和时间 "MM/DD HH:mm"
    return `${month}/${day} ${timeStr_formatted}`
  }
}

// 检查卡片数据是否有效
const hasCardData = (cardData: CardData | null | undefined): boolean => {
  if (!cardData) return false
  // 检查5步骤内容
  if (
    cardData.step1_emotion_mirror ||
    cardData.step1_problem_restate ||
    cardData.step2_breakdown ||
    cardData.step3_explanation ||
    cardData.step4_suggestions ||
    cardData.step5_summary
  ) {
    return true
  }
  // 检查旧版格式
  return !!(
    cardData.theme ||
    cardData.emotion_echo ||
    cardData.clarification ||
    (cardData.suggestion && 
      (Array.isArray(cardData.suggestion) ? cardData.suggestion.length > 0 : cardData.suggestion.trim().length > 0))
  )
}

// 监听会话变化，自动刷新会话列表
watch(sessionId, () => {
  loadSessions()
})

const handleSend = async () => {
  if (!input.value.trim() || loading.value) return

  const userMessage: ChatMessage = {
    role: 'user',
    content: input.value.trim(),
  }

  const newMessages = [...messages.value, userMessage]
  messages.value = newMessages
  const currentInput = input.value.trim()
  input.value = ''
  const epoch = ++viewEpoch
  loading.value = true

  try {
    const response = await sendChatMessage({
      session_id: sessionId.value,
      messages: newMessages,
      experience_mode: selectedExperienceMode.value,
      ai_style: selectedAIStyle.value,
      chat_mode: selectedChatMode.value,
    })
    if (epoch !== viewEpoch) { loadSessions(); return }

    if (response.error) {
      console.error('API Error:', response.error)
      message.error(`${t('common.error')}: ${response.error.message}`)
      // 恢复输入
      if (!input.value.trim()) input.value = currentInput
      return
    }

    if (response.data) {
      const data = response.data
      sessionId.value = data.session_id
      todayEmotion.value = data.emotion
      lastRiskLevel.value = data.risk_level

      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: data.reply,
        card_data: data.card_data || null,
        should_show_card_button: data.should_show_card_button || false,
        should_show_satisfaction_buttons: data.should_show_satisfaction_buttons || false,
      }

      messages.value = [...newMessages, assistantMessage]
      
      // 更新是否显示"开始关心"按钮的状态
      shouldShowCardButton.value = data.should_show_card_button || false
      shouldShowSatisfactionButtons.value = data.should_show_satisfaction_buttons || false
      scrollToBottom()
      // 刷新会话列表
      loadSessions()
      
      // 如果检测到高风险，显示额外提示
      if (data.risk_level === 'high') {
        message.warning(t('chat.highRiskDetected'))
      }
    }
  } catch (error) {
    if (epoch !== viewEpoch) return
    console.error('Request failed:', error)
    message.error(t('chat.sendFailed'))
    // 恢复输入
    if (!input.value.trim()) input.value = currentInput
  } finally {
    if (epoch === viewEpoch) loading.value = false
  }
}

const handleKeyPress = (e: KeyboardEvent) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

// 处理满意度按钮点击
const handleSatisfaction = async (satisfied: boolean) => {
  if (loading.value) return
  if (!sessionId.value) {
    message.error(t('chat.noSession') || '没有会话ID')
    return
  }

  const epoch = ++viewEpoch
  loading.value = true
  
  // 立即隐藏最后一条AI消息的满意度按钮，防止重复点击
  const lastAssistantMsg = [...messages.value].reverse().find(msg => msg.role === 'assistant')
  if (lastAssistantMsg) {
    lastAssistantMsg.should_show_satisfaction_buttons = false
  }
  
  try {
    // 发送特殊消息，表示用户对小结的满意度
    // 注意：这个消息不会显示给用户，只是用于后端处理
    const satisfactionMessage: ChatMessage = {
      role: 'user',
      content: satisfied ? '[SATISFACTION:满意]' : '[SATISFACTION:不满意]',
    }

    const newMessages = [...messages.value, satisfactionMessage]
    // 不立即更新messages，等后端回复后再更新，这样特殊消息不会显示

    const response = await sendChatMessage({
      session_id: sessionId.value,
      messages: newMessages,
      experience_mode: selectedExperienceMode.value,
      ai_style: selectedAIStyle.value,
      chat_mode: selectedChatMode.value,
    })
    if (epoch !== viewEpoch) { loadSessions(); return }

    if (response.error) {
      console.error('API Error:', response.error)
      message.error(`${t('common.error')}: ${response.error.message}`)
      return
    }

      if (response.data) {
      const data = response.data
      sessionId.value = data.session_id
      todayEmotion.value = data.emotion
      lastRiskLevel.value = data.risk_level

      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: data.reply,
        card_data: data.card_data || null,
        should_show_card_button: data.should_show_card_button || false,
        should_show_satisfaction_buttons: data.should_show_satisfaction_buttons || false,
      }

      // 对于满意度反馈，不显示用户的特殊消息，只显示AI的回复
      // 这样界面更干净，用户体验更好
      messages.value = [...messages.value, assistantMessage]
      
      // 更新按钮状态
      shouldShowCardButton.value = data.should_show_card_button || false
      scrollToBottom()
      // 刷新会话列表
      loadSessions()
      
      // 如果检测到高风险，显示额外提示
      if (data.risk_level === 'high') {
        message.warning(t('chat.highRiskDetected'))
      }
    }
  } catch (error) {
    if (epoch !== viewEpoch) return
    console.error('Satisfaction feedback failed:', error)
    message.error(t('chat.sendFailed'))
  } finally {
    if (epoch === viewEpoch) loading.value = false
  }
}

// 处理生成卡片按钮点击
const handleGenerateCard = async () => {
  if (loading.value) return
  if (!sessionId.value) {
    message.error(t('chat.noSession') || '没有会话ID')
    return
  }

  const epoch = ++viewEpoch
  loading.value = true
  try {
    const response = await generateCard(sessionId.value)
    if (epoch !== viewEpoch) { loadSessions(); return }

    if (response.error) {
      console.error('Generate Card Error:', response.error)
      message.error(`${t('common.error')}: ${response.error.message}`)
      return
    }

    if (response.data) {
      const data = response.data
      todayEmotion.value = data.emotion
      lastRiskLevel.value = data.risk_level

      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: data.reply,
        card_data: data.card_data || null,
        should_show_card_button: false, // 生成卡片后不再显示按钮
      }

      messages.value = [...messages.value, assistantMessage]
      shouldShowCardButton.value = false // 隐藏按钮
      shouldShowSatisfactionButtons.value = false // 隐藏满意度按钮
      scrollToBottom()
      // 刷新会话列表
      loadSessions()
      
      // 如果检测到高风险，显示额外提示
      if (data.risk_level === 'high') {
        message.warning(t('chat.highRiskDetected'))
      }
    }
  } catch (error) {
    if (epoch !== viewEpoch) return
    console.error('Generate Card failed:', error)
    message.error(t('chat.generateCardFailed') || '生成卡片失败')
  } finally {
    if (epoch === viewEpoch) loading.value = false
  }
}

const getEmotionLabel = (emotion: string | null) => {
  if (!emotion) return t('emotions.none')
  const emotionKey = emotion as keyof typeof import('@/i18n/zh').default.emotions
  try {
    return t(`emotions.${emotionKey}`) || emotion
  } catch {
    return emotion
  }
}

const openCardFullscreen = (cardData: CardData | null | undefined) => {
  if (!cardData) {
    console.warn('openCardFullscreen: cardData is null or undefined')
    return
  }
  
  // 检查卡片数据是否有效
  if (!hasCardData(cardData)) {
    console.warn('openCardFullscreen: cardData is invalid', cardData)
    message.warning(t('chat.invalidCardData') || '卡片数据无效')
    return
  }
  
  console.log('Opening fullscreen with card data:', cardData)
  
  // 使用深拷贝确保数据独立性
  fullscreenCardData.value = JSON.parse(JSON.stringify(cardData))
  cardFullscreenVisible.value = true
  
  previousBodyOverflow = document.body.style.overflow
  document.body.style.overflow = 'hidden'
  document.body.classList.add(FULLSCREEN_BODY_CLASS)
  
  // 确保 DOM 更新
  nextTick(() => {
    console.log('Fullscreen opened, visible:', cardFullscreenVisible.value, 'data:', fullscreenCardData.value)
    // 确保滚动到顶部
    const cardElement = document.querySelector('.heart-card-fullscreen')
    if (cardElement) {
      cardElement.scrollTop = 0
    }
  })
}

const closeCardFullscreen = () => {
  cardFullscreenVisible.value = false
  fullscreenCardData.value = null
  document.body.style.overflow = previousBodyOverflow
  document.body.classList.remove(FULLSCREEN_BODY_CLASS)
}

const sanitizeFileName = (value: string) => {
  return value.replace(/[\\/:*?"<>|]/g, '_')
}

// 模板选项
const templateOptions = [
  { label: '基础模板', value: 'basic' as CardTemplate, icon: '📄' },
  { label: '星空漫游模板', value: 'starry' as CardTemplate, icon: '⭐' },
  { label: '蓝海前行模板', value: 'ocean' as CardTemplate, icon: '🌊' },
  { label: '中国古风模板', value: 'ancient' as CardTemplate, icon: '🏮' },
  { label: '科幻未来模板', value: 'sci-fi' as CardTemplate, icon: '🚀' },
  { label: '想象糖果棉花城模板', value: 'candy' as CardTemplate, icon: '🍬' },
]

// 用于存储当前对话框选中的模板
const exportTemplateSelection = ref<CardTemplate>('basic')

const handleExportCard = (cardData?: CardData | null) => {
  if (!cardData) return
  
  // 直接使用默认模板导出，不显示选择对话框
  try {
    const html = generateCardHtml(cardData, 'basic')
    const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const title = sanitizeFileName(cardData.theme?.trim() || t('chat.cardTitle'))
    const date = new Date().toISOString().split('T')[0]
    const link = document.createElement('a')
    link.href = url
    link.download = `${title}-${date}.html`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    message.success(t('chat.exportSuccess'))
  } catch (error) {
    console.error(error)
    message.error(t('chat.exportFailed'))
  }
  
  // 以下代码保留，供将来恢复模板选择功能时使用
  // // 保存要导出的卡片数据
  // currentExportCardData.value = cardData
  // // 重置选中的模板
  // exportTemplateSelection.value = 'basic'
  // // 显示模板选择对话框
  // templateSelectVisible.value = true
}

const handleTemplateExport = () => {
  if (!currentExportCardData.value) return false
  
  try {
    const html = generateCardHtml(currentExportCardData.value, exportTemplateSelection.value)
    const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const title = sanitizeFileName(currentExportCardData.value.theme?.trim() || t('chat.cardTitle'))
    const date = new Date().toISOString().split('T')[0]
    const link = document.createElement('a')
    link.href = url
    link.download = `${title}-${date}.html`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    message.success(t('chat.exportSuccess'))
    templateSelectVisible.value = false
    currentExportCardData.value = null
    return true
  } catch (error) {
    console.error(error)
    message.error(t('chat.exportFailed'))
    return false
  }
}

onUnmounted(() => {
  viewEpoch++
  sessionListEpoch++
  document.body.style.overflow = previousBodyOverflow
  document.body.classList.remove(FULLSCREEN_BODY_CLASS)
})
</script>

<style scoped>
@import '../styles/design-system.css';

.chat-layout {
  display: flex;
  height: calc(100vh - 180px);
  min-height: 600px;
  gap: var(--spacing-md);
}

.sidebar {
  width: 280px;
  min-width: 280px;
  background: var(--bg-elevated);
  border: var(--border-width-thin) solid var(--border-color-light);
  border-radius: var(--radius-2xl);
  box-shadow: var(--shadow-warm-md);
  backdrop-filter: blur(20px);
  display: flex;
  flex-direction: column;
  transition: all var(--transition-base);
  overflow: hidden;
}

.sidebar-collapsed {
  width: 60px;
  min-width: 60px;
}

.sidebar-header {
  padding: var(--spacing-md);
  display: flex;
  gap: var(--spacing-sm);
  align-items: center;
  border-bottom: var(--border-width-thin) solid var(--border-color-light);
  flex-shrink: 0;
}

.sidebar-toggle {
  flex-shrink: 0;
}

.new-chat-button {
  flex: 1;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-secondary) 100%) !important;
  border: none !important;
  border-color: transparent !important;
  border-radius: var(--radius-lg) !important;
  font-weight: var(--font-weight-semibold);
  transition: all var(--transition-base);
  outline: none !important;
}

/* 移除新对话按钮的所有边框和验证状态边框 */
.new-chat-button :deep(.n-button__border),
.new-chat-button :deep(.n-button__state-border),
.new-chat-button :deep(.n-button__border--focus),
.new-chat-button :deep(.n-button__border--hover),
.new-chat-button :deep(.n-button__border--active),
.new-chat-button :deep(.n-button__border--success),
.new-chat-button :deep(.n-button__border--warning),
.new-chat-button :deep(.n-button__border--error) {
  border: none !important;
  border-color: transparent !important;
  display: none !important;
}

.new-chat-button :deep(button),
.new-chat-button :deep(.n-button),
.new-chat-button :deep(.n-button *) {
  border: none !important;
  border-color: transparent !important;
  outline: none !important;
}

.new-chat-button :deep(button:focus),
.new-chat-button :deep(button:focus-visible),
.new-chat-button :deep(.n-button--focus),
.new-chat-button :deep(.n-button--focus *) {
  border: none !important;
  border-color: transparent !important;
  outline: none !important;
  box-shadow: none !important;
}

.new-chat-button :deep(.n-button--success),
.new-chat-button :deep(.n-button--success *),
.new-chat-button :deep(.n-button--warning),
.new-chat-button :deep(.n-button--warning *),
.new-chat-button :deep(.n-button--error),
.new-chat-button :deep(.n-button--error *) {
  border: none !important;
  border-color: transparent !important;
  box-shadow: none !important;
}

.new-chat-button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: var(--shadow-warm-md) !important;
}

.new-chat-button:focus,
.new-chat-button:focus-visible {
  outline: none !important;
  box-shadow: var(--shadow-warm-md) !important;
}

.sidebar-collapsed .new-chat-button {
  display: none;
}

.sidebar-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-md);
  display: flex;
  flex-direction: column;
}

.sidebar-content::-webkit-scrollbar {
  width: 6px;
}

.sidebar-content::-webkit-scrollbar-track {
  background: var(--color-neutral-100);
  border-radius: var(--radius-lg);
}

.sidebar-content::-webkit-scrollbar-thumb {
  background: var(--color-primary-light);
  border-radius: var(--radius-lg);
}

.sidebar-content::-webkit-scrollbar-thumb:hover {
  background: var(--color-primary);
}

.sidebar-title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin-bottom: var(--spacing-md);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  opacity: 0.85;
}

.sidebar-loading,
.sidebar-empty {
  text-align: center;
  padding: var(--spacing-xl) var(--spacing-md);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-normal);
}

.session-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.session-item {
  padding: var(--spacing-md) var(--spacing-md);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: all var(--transition-base);
  border: var(--border-width-thin) solid transparent;
  background: var(--color-primary-lighter);
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-sm);
}

.session-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: linear-gradient(180deg, var(--color-primary) 0%, var(--color-secondary) 100%);
  transform: scaleY(0);
  transition: transform var(--transition-base);
}

.session-item:hover {
  background: var(--color-primary-light);
  transform: translateX(4px);
  border-color: var(--border-color-base);
}

.session-item:hover::before {
  transform: scaleY(1);
}

.session-item.active {
  background: linear-gradient(135deg, var(--color-primary-lighter) 0%, var(--color-secondary-lighter) 100%);
  border-color: var(--border-color-base);
  box-shadow: var(--shadow-warm-sm);
}

.session-item.active::before {
  transform: scaleY(1);
}

.session-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.session-preview {
  font-size: var(--font-size-sm);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: var(--line-height-normal);
}

.session-item.active .session-preview {
  color: var(--text-primary);
  font-weight: var(--font-weight-semibold);
}

.session-time {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  font-weight: var(--font-weight-normal);
}

.session-item.active .session-time {
  color: var(--text-primary);
  font-weight: var(--font-weight-medium);
}

.session-delete-button {
  opacity: 0;
  transition: opacity var(--transition-base);
  flex-shrink: 0;
}

.session-item:hover .session-delete-button {
  opacity: 1;
}

.session-delete-button:hover {
  background-color: var(--color-error-lighter) !important;
  color: var(--color-error) !important;
}

.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
  min-width: 0;
}

.emotion-card {
  background: var(--bg-elevated) !important;
  border: var(--border-width-thin) solid var(--border-color-light) !important;
  border-radius: var(--radius-2xl) !important;
  box-shadow: var(--shadow-warm-md) !important;
  transition: all var(--transition-smooth) !important;
  backdrop-filter: blur(20px);
  flex-shrink: 0;
  outline: none !important;
}

.emotion-card :deep(.n-card) {
  outline: none !important;
  border: none !important;
}

.emotion-card :deep(.n-card__content) {
  outline: none !important;
}

.emotion-card:hover {
  box-shadow: var(--shadow-warm-lg) !important;
  border-color: var(--border-color-base) !important;
}

.emotion-card-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-sm) 0;
  gap: var(--spacing-md);
  flex-wrap: wrap;
}

.emotion-left {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.emotion-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  background: linear-gradient(135deg, var(--color-primary-lighter) 0%, var(--color-secondary-lighter) 100%);
  border-radius: var(--radius-xl);
  border: var(--border-width-thin) solid var(--border-color-light);
}

.emotion-icon {
  font-size: var(--font-size-2xl);
  filter: drop-shadow(0 2px 6px rgba(232, 180, 184, 0.4));
  animation: float 3s ease-in-out infinite;
}

.emotion-label {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  letter-spacing: 0.3px;
}

.emotion-badge {
  padding: var(--spacing-sm) var(--spacing-lg);
  background: linear-gradient(135deg, var(--color-primary-lighter) 0%, var(--color-secondary-lighter) 100%);
  border-radius: var(--radius-2xl);
  border: var(--border-width-thin) solid var(--border-color-base);
  box-shadow: var(--shadow-warm-sm);
  transition: all var(--transition-base);
}

.emotion-badge:hover {
  transform: scale(1.05);
  box-shadow: var(--shadow-warm-md);
}

.emotion-text {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
  /* 使用更深的渐变以确保可读性 */
  background: linear-gradient(135deg, var(--color-primary-darker) 0%, var(--color-primary-dark) 50%, var(--color-primary-darker) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.config-selectors-inline {
  display: flex;
  gap: var(--spacing-sm);
  align-items: center;
  flex-wrap: nowrap;
  margin-left: auto;
}

.inline-selector {
  min-width: 120px;
  flex-shrink: 1;
}

/* 第一个选择器可以自适应宽度 */
.config-selectors-inline .inline-selector:first-child {
  min-width: 150px;
  flex: 1 1 auto;
}

/* 可爱温暖的选择器样式 */
.inline-selector :deep(.n-base-selection) {
  border-radius: 20px !important;
  border: 2px solid rgba(255, 182, 193, 0.4) !important;
  background: linear-gradient(135deg, var(--color-primary-lighter) 0%, var(--color-secondary-lighter) 100%) !important;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
  box-shadow: 0 2px 8px rgba(255, 182, 193, 0.15) !important;
  padding: 6px 12px !important;
  font-size: 13px !important;
  color: var(--text-primary) !important;
  min-height: 36px !important;
}

/* 移除所有边框元素（包括验证状态的绿色边框） */
.inline-selector :deep(.n-base-selection__border),
.inline-selector :deep(.n-base-selection__state-border),
.inline-selector :deep(.n-base-selection__border--success),
.inline-selector :deep(.n-base-selection__border--warning),
.inline-selector :deep(.n-base-selection__border--error),
.inline-selector :deep(.n-base-selection__border--focus),
.inline-selector :deep(.n-base-selection__border--active),
.inline-selector :deep(.n-base-selection__border--hover) {
  display: none !important;
  border: none !important;
  border-color: transparent !important;
  box-shadow: none !important;
}

/* 移除验证状态的绿色边框和背景 */
.inline-selector :deep(.n-select--success .n-base-selection),
.inline-selector :deep(.n-select--success .n-base-selection__border),
.inline-selector :deep(.n-select--warning .n-base-selection),
.inline-selector :deep(.n-select--warning .n-base-selection__border),
.inline-selector :deep(.n-select--error .n-base-selection),
.inline-selector :deep(.n-select--error .n-base-selection__border),
.inline-selector :deep(.n-base-selection--success),
.inline-selector :deep(.n-base-selection--warning),
.inline-selector :deep(.n-base-selection--error) {
  border-color: rgba(255, 182, 193, 0.4) !important;
  box-shadow: 0 2px 8px rgba(255, 182, 193, 0.15) !important;
  background: linear-gradient(135deg, var(--color-primary-lighter) 0%, var(--color-secondary-lighter) 100%) !important;
}

/* 移除所有可能的绿色 box-shadow */
.inline-selector :deep(.n-select--success),
.inline-selector :deep(.n-select--success *),
.inline-selector :deep(.n-select--warning),
.inline-selector :deep(.n-select--warning *),
.inline-selector :deep(.n-select--error),
.inline-selector :deep(.n-select--error *) {
  box-shadow: none !important;
}

.inline-selector :deep(.n-select--success .n-base-selection),
.inline-selector :deep(.n-select--warning .n-base-selection),
.inline-selector :deep(.n-select--error .n-base-selection) {
  box-shadow: 0 2px 8px rgba(255, 182, 193, 0.15) !important;
}

.inline-selector :deep(.n-base-selection:hover) {
  border-color: rgba(255, 182, 193, 0.7) !important;
  background: linear-gradient(135deg, var(--color-primary-light) 0%, var(--color-secondary-light) 100%) !important;
  box-shadow: 0 4px 12px rgba(255, 182, 193, 0.25) !important;
  transform: translateY(-1px);
  color: var(--text-primary) !important;
}

.inline-selector :deep(.n-base-selection--active),
.inline-selector :deep(.n-base-selection--focus) {
  border-color: rgba(255, 105, 180, 0.6) !important;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-secondary) 100%) !important;
  box-shadow: 0 4px 16px rgba(255, 182, 193, 0.35), 0 0 0 3px rgba(255, 182, 193, 0.2) !important;
  color: var(--text-primary) !important;
}

.inline-selector :deep(.n-base-selection__placeholder) {
  color: var(--text-disabled);
  font-weight: 500;
}

.inline-selector :deep(.n-base-selection__input) {
  color: var(--text-primary) !important;
  font-weight: 500;
}

.inline-selector :deep(.n-base-selection__arrow) {
  color: var(--text-secondary);
  transition: all 0.3s ease;
}

.inline-selector :deep(.n-base-selection:hover .n-base-selection__arrow) {
  color: var(--color-primary);
  transform: scale(1.1);
}

/* 下拉菜单样式 - 使用全局样式覆盖，确保圆角更大，无白色背景 */
.inline-selector :deep(.n-base-select-menu),
.inline-selector :deep(.n-select-menu),
.inline-selector :deep(.n-popover),
.inline-selector :deep(.n-popover__content),
.inline-selector :deep(.n-base-select-menu__content),
.inline-selector :deep(.n-select-menu__content),
.inline-selector :deep(.n-base-select-menu__wrapper),
.inline-selector :deep(.n-select-menu__wrapper) {
  border-radius: var(--radius-2xl) !important;
  border: 2px solid rgba(255, 182, 193, 0.3) !important;
  background: linear-gradient(135deg, var(--color-primary-lighter) 0%, var(--color-secondary-lighter) 100%) !important;
  box-shadow: 0 8px 24px rgba(255, 182, 193, 0.2) !important;
  backdrop-filter: blur(10px);
  overflow: hidden !important;
}

/* 彻底移除所有可能的白色背景 */
.inline-selector :deep(.n-base-select-menu *),
.inline-selector :deep(.n-select-menu *),
.inline-selector :deep(.n-popover *),
.inline-selector :deep(.n-popover__content *) {
  background-color: transparent !important;
}

/* 确保下拉菜单内部容器也是圆角，并移除白色背景 */
.inline-selector :deep(.n-base-select-menu .n-scrollbar),
.inline-selector :deep(.n-select-menu .n-scrollbar),
.inline-selector :deep(.n-base-select-menu .n-scrollbar-content),
.inline-selector :deep(.n-select-menu .n-scrollbar-content),
.inline-selector :deep(.n-base-select-menu .n-scrollbar__container),
.inline-selector :deep(.n-select-menu .n-scrollbar__container),
.inline-selector :deep(.n-base-select-menu .n-scrollbar__view),
.inline-selector :deep(.n-select-menu .n-scrollbar__view) {
  border-radius: var(--radius-2xl) !important;
  background: transparent !important;
}

/* 移除下拉菜单中的白色背景，但保留渐变背景 */
.inline-selector :deep(.n-base-select-menu .n-list),
.inline-selector :deep(.n-select-menu .n-list),
.inline-selector :deep(.n-base-select-menu .n-list-item),
.inline-selector :deep(.n-select-menu .n-list-item),
.inline-selector :deep(.n-base-select-menu__empty),
.inline-selector :deep(.n-select-menu__empty) {
  background: transparent !important;
}

/* 确保主容器有渐变背景 */
.inline-selector :deep(.n-base-select-menu),
.inline-selector :deep(.n-select-menu),
.inline-selector :deep(.n-popover) {
  background: linear-gradient(135deg, var(--color-primary-lighter) 0%, var(--color-secondary-lighter) 100%) !important;
  background-color: transparent !important;
}

.inline-selector :deep(.n-base-select-option),
.inline-selector :deep(.n-select-option),
.inline-selector :deep(.n-base-select-option__content) {
  border-radius: 12px !important;
  margin: 4px 8px !important;
  transition: all 0.2s ease !important;
  color: var(--text-primary) !important;
  background: transparent !important;
  background-color: transparent !important;
}

.inline-selector :deep(.n-base-select-option:hover),
.inline-selector :deep(.n-select-option:hover) {
  background: linear-gradient(135deg, var(--color-primary-light) 0%, var(--color-secondary-light) 100%) !important;
  transform: translateX(4px);
}

.inline-selector :deep(.n-base-select-option--selected),
.inline-selector :deep(.n-select-option--selected) {
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-secondary) 100%) !important;
  color: var(--text-primary) !important;
  font-weight: 600;
}

.selector-group {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
  flex: 1;
  min-width: 200px;
}

.selector-label {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.style-selector {
  width: 100%;
}

.style-selector :deep(.n-base-selection) {
  border-radius: var(--radius-lg);
  border: var(--border-width-thin) solid var(--border-color-base);
  background: var(--bg-elevated);
  transition: all var(--transition-base);
}

.style-selector :deep(.n-base-selection:hover) {
  border-color: var(--color-primary);
}

.style-selector :deep(.n-base-selection--active) {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-lighter);
}


.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-lg) var(--spacing-md);
  scroll-behavior: smooth;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
  min-height: 0;
}

.messages-container::-webkit-scrollbar {
  width: 8px;
}

.messages-container::-webkit-scrollbar-track {
  background: var(--color-neutral-100);
  border-radius: var(--radius-lg);
}

.messages-container::-webkit-scrollbar-thumb {
  background: var(--color-primary-light);
  border-radius: var(--radius-lg);
}

.messages-container::-webkit-scrollbar-thumb:hover {
  background: var(--color-primary);
}

.welcome-section {
  text-align: center;
  padding: var(--spacing-3xl) var(--spacing-md);
  animation: welcomeFadeIn var(--transition-smooth);
}

@keyframes welcomeFadeIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.app-logo-wrapper {
  position: relative;
  display: inline-block;
  margin-bottom: var(--spacing-md);
}

.welcome-icon {
  width: 120px;
  height: 120px;
  object-fit: contain;
  filter: drop-shadow(0 4px 8px rgba(232, 180, 184, 0.3));
  animation: float 3s ease-in-out infinite;
}

.logo-glow {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 140px;
  height: 140px;
  background: radial-gradient(circle, rgba(232, 180, 184, 0.2) 0%, transparent 70%);
  border-radius: 50%;
  z-index: -1;
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 0.5; transform: translate(-50%, -50%) scale(1); }
  50% { opacity: 0.8; transform: translate(-50%, -50%) scale(1.1); }
}

@keyframes float {
  0%, 100% { transform: translateY(0px); }
  50% { transform: translateY(-10px); }
}

.welcome-title {
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-semibold);
  margin-bottom: var(--spacing-md);
  /* 使用更深的渐变以确保可读性 */
  background: linear-gradient(135deg, var(--color-primary-darker) 0%, var(--color-primary-dark) 50%, var(--color-primary-darker) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.welcome-desc {
  font-size: var(--font-size-base);
  color: var(--text-secondary);
  line-height: var(--line-height-relaxed);
  font-weight: var(--font-weight-normal);
}

.message-wrapper {
  display: flex;
  animation: slideIn 0.3s ease;
  margin-bottom: var(--spacing-xs);
}

.message-wrapper:last-of-type {
  margin-bottom: 0;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.user-message {
  justify-content: flex-end;
  padding-left: var(--spacing-xl);
}

.assistant-message {
  justify-content: flex-start;
  padding-right: var(--spacing-xl);
}

.message-bubble {
  max-width: 75%;
  padding: var(--spacing-md) var(--spacing-lg);
  word-wrap: break-word;
  position: relative;
  box-shadow: var(--shadow-md);
  transition: all var(--transition-base);
  line-height: var(--line-height-relaxed);
  animation: messageSlideIn var(--transition-smooth);
  border-radius: var(--radius-2xl);
}

@keyframes messageSlideIn {
  from {
    opacity: 0;
    transform: translateY(10px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.message-bubble:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-lg);
}

.user-bubble {
  /* 使用更浅更温暖的渐变 */
  background: linear-gradient(135deg, var(--color-primary-dark) 0%, var(--color-primary) 50%, var(--color-secondary) 100%);
  color: var(--text-inverse);
  /* 精致的圆角：右上和左上大圆角，右下小圆角，左下中等圆角 */
  border-top-left-radius: var(--radius-2xl);
  border-top-right-radius: var(--radius-2xl);
  border-bottom-left-radius: var(--radius-lg);
  border-bottom-right-radius: var(--radius-md);
  box-shadow: var(--shadow-warm-md), 
              0 2px 8px rgba(232, 180, 184, 0.2);
  position: relative;
  overflow: hidden;
}

.user-bubble::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
  transition: left 0.5s ease;
}

.user-bubble:hover::before {
  left: 100%;
}

.assistant-bubble {
  background: var(--bg-elevated);
  color: var(--text-primary);
  border: var(--border-width-thin) solid var(--border-color-base);
  /* 精致的圆角：左上和左下大圆角，右上小圆角，右下中等圆角 */
  border-top-left-radius: var(--radius-2xl);
  border-top-right-radius: var(--radius-lg);
  border-bottom-left-radius: var(--radius-xl);
  border-bottom-right-radius: var(--radius-lg);
  backdrop-filter: blur(15px);
  box-shadow: var(--shadow-sm),
              0 1px 3px rgba(232, 180, 184, 0.08);
  position: relative;
}

.assistant-bubble::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(135deg, var(--color-primary-lighter) 0%, transparent 100%);
  pointer-events: none;
  border-radius: inherit;
  opacity: 0.15;
}

.message-content {
  margin: 0;
  line-height: 1.7;
  font-size: var(--font-size-base);
  white-space: pre-wrap;
  word-break: break-word;
  letter-spacing: 0.01em;
  position: relative;
  z-index: 1;
}

.user-bubble .message-content {
  color: #FFFFFF;
  /* 适度的文字阴影以提高可读性 */
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.25),
               0 0 1px rgba(0, 0, 0, 0.15);
  font-weight: var(--font-weight-medium);
}

.assistant-bubble .message-content {
  color: var(--text-primary);
}

.assistant-card {
  max-width: 100%;
  margin: 0;
}

.assistant-card-wrapper {
  position: relative;
}

/* 引导阶段的白色卡片样式 */
.guiding-card {
  background: rgba(255, 255, 255, 0.95);
  border-radius: var(--radius-2xl);
  padding: var(--spacing-xl);
  box-shadow: 
    0 4px 20px rgba(0, 0, 0, 0.08),
    0 2px 8px rgba(0, 0, 0, 0.04),
    inset 0 1px 0 rgba(255, 255, 255, 0.8);
  border: 1px solid rgba(0, 0, 0, 0.08);
  position: relative;
  overflow: hidden;
  backdrop-filter: blur(10px);
  max-width: 100%;
}

.guiding-card::before {
  content: '';
  position: absolute;
  top: -50%;
  right: -50%;
  width: 200%;
  height: 200%;
  background: radial-gradient(
    circle,
    rgba(232, 180, 184, 0.05) 0%,
    transparent 70%
  );
  pointer-events: none;
}

.guiding-card-content {
  margin: 0;
  line-height: 1.8;
  font-size: var(--font-size-base);
  white-space: pre-wrap;
  word-break: break-word;
  letter-spacing: 0.01em;
  color: var(--text-primary);
  position: relative;
  z-index: 1;
}

.card-action-buttons {
  position: absolute;
  top: var(--spacing-sm);
  right: var(--spacing-sm);
  display: flex;
  gap: var(--spacing-xs);
  z-index: 2;
}

.card-action-button {
  background: rgba(255, 255, 255, 0.85) !important;
  box-shadow: 0 4px 12px rgba(232, 180, 184, 0.2) !important;
  transition: transform var(--transition-base), box-shadow var(--transition-base);
  color: var(--color-primary-dark) !important;
}

.card-action-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(232, 180, 184, 0.3) !important;
}

.card-export-button {
  border: 1px solid rgba(232, 180, 184, 0.4) !important;
}

.card-fullscreen-toggle {
  border: 1px solid rgba(232, 180, 184, 0.2) !important;
}

.template-select-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  padding: 16px 0;
  min-width: 500px;
}

.template-option {
  padding: 20px 16px;
  border: 2px solid #e0e0e0;
  border-radius: 12px;
  cursor: pointer;
  background-color: #fff;
  transition: all 0.2s;
  text-align: center;
}

.template-option:hover {
  border-color: #18a058;
  background-color: #f0f9ff;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(24, 160, 88, 0.15);
}

.template-option.active {
  border-color: #18a058;
  background-color: #f0f9ff;
  box-shadow: 0 2px 8px rgba(24, 160, 88, 0.2);
}

.template-icon {
  font-size: 32px;
  margin-bottom: 12px;
}

.template-label {
  font-weight: 500;
  font-size: 14px;
  color: #333;
}

.loading-bubble {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-md) var(--spacing-lg);
  min-height: 48px;
}

.loading-dots {
  display: flex;
  gap: var(--spacing-xs);
}

.loading-dots span {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
  background: var(--color-primary);
  animation: bounce 1.4s ease-in-out infinite;
}

.loading-dots span:nth-child(1) {
  animation-delay: 0s;
}

.loading-dots span:nth-child(2) {
  animation-delay: 0.2s;
}

.loading-dots span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes bounce {
  0%, 80%, 100% {
    transform: scale(0.8);
    opacity: 0.5;
  }
  40% {
    transform: scale(1.2);
    opacity: 1;
  }
}

.loading-text {
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  letter-spacing: 0.3px;
}

.input-card {
  background: var(--bg-elevated) !important;
  border: var(--border-width-thin) solid var(--border-color-light) !important;
  border-radius: var(--radius-2xl) !important;
  box-shadow: var(--shadow-warm-md) !important;
  backdrop-filter: blur(20px);
  flex-shrink: 0;
  transition: all var(--transition-base);
  outline: none !important;
}

.input-card :deep(.n-card) {
  outline: none !important;
  border: none !important;
}

.input-card :deep(.n-card__content) {
  outline: none !important;
  padding: var(--spacing-md) !important;
}


.risk-warning {
  margin-bottom: var(--spacing-md);
  animation: slideDown 0.3s ease;
}

.card-button-wrapper {
  margin-bottom: var(--spacing-md);
  animation: slideDown 0.3s ease;
}

.satisfaction-buttons-wrapper {
  margin-bottom: var(--spacing-md);
  animation: slideDown 0.3s ease;
}

/* 消息内的满意度按钮 */
.satisfaction-buttons-in-message {
  margin-top: var(--spacing-md);
  padding: 0 var(--spacing-md);
  animation: slideDown 0.3s ease;
}

.satisfaction-buttons {
  display: flex;
  gap: var(--spacing-md);
  align-items: center;
  justify-content: center;
}

.satisfaction-button {
  flex: 1;
  font-weight: var(--font-weight-semibold);
  transition: all var(--transition-base);
  border-radius: var(--radius-xl);
}

.satisfaction-button-yes {
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-secondary) 100%) !important;
  border: none !important;
  box-shadow: 0 4px 12px rgba(232, 180, 184, 0.3);
}

.satisfaction-button-yes:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(232, 180, 184, 0.4);
}

.satisfaction-button-no {
  background: var(--bg-elevated) !important;
  border: var(--border-width-thin) solid var(--border-color-base) !important;
  color: var(--text-primary) !important;
  box-shadow: var(--shadow-sm);
}

.satisfaction-button-no:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
  border-color: var(--color-primary) !important;
}

.generate-card-button {
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-secondary) 100%) !important;
  border: none !important;
  font-weight: var(--font-weight-semibold);
  transition: all var(--transition-base);
  box-shadow: 0 4px 12px rgba(232, 180, 184, 0.3);
}

.generate-card-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(232, 180, 184, 0.4);
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.input-card:hover {
  box-shadow: var(--shadow-warm-lg) !important;
}

.input-wrapper {
  display: flex;
  gap: var(--spacing-lg);
  align-items: flex-end;
  padding: var(--spacing-sm) 0;
}

.chat-input {
  flex: 1;
}

/* 移除所有可能的绿色边框和焦点样式 */
.chat-input :deep(.n-input) {
  outline: none !important;
  border: none !important;
  border-color: transparent !important;
}

.chat-input :deep(.n-input:focus) {
  outline: none !important;
  box-shadow: none !important;
  border: none !important;
  border-color: transparent !important;
}

.chat-input :deep(.n-input:focus-within) {
  outline: none !important;
  border: none !important;
  border-color: transparent !important;
}

.chat-input :deep(.n-input-wrapper) {
  outline: none !important;
  border: none !important;
  border-color: transparent !important;
  padding: 0 !important;
  margin: 0 !important;
}

.chat-input :deep(.n-input-wrapper:focus-within) {
  outline: none !important;
  border: none !important;
  border-color: transparent !important;
  box-shadow: none !important;
  padding: 0 !important;
  margin: 0 !important;
}

.chat-input :deep(.n-input-wrapper:focus) {
  outline: none !important;
  border: none !important;
  border-color: transparent !important;
  box-shadow: none !important;
  padding: 0 !important;
  margin: 0 !important;
}

.chat-input :deep(.n-input__border) {
  border: none !important;
  border-color: transparent !important;
  outline: none !important;
}

.chat-input :deep(.n-input__state-border) {
  border: none !important;
  border-color: transparent !important;
  outline: none !important;
}

.chat-input :deep(.n-input__border--focus) {
  border: none !important;
  border-color: transparent !important;
  outline: none !important;
}

.chat-input :deep(.n-input__border--active) {
  border: none !important;
  border-color: transparent !important;
  outline: none !important;
}

/* 覆盖聚焦状态的所有边框 */
.chat-input :deep(.n-input-wrapper--focus),
.chat-input :deep(.n-input-wrapper--focus *),
.chat-input :deep(.n-input--focus),
.chat-input :deep(.n-input--focus *),
.chat-input :deep(.n-input-wrapper--focus .n-input__border),
.chat-input :deep(.n-input-wrapper--focus .n-input__state-border),
.chat-input :deep(.n-input-wrapper--focus .n-input__border--focus) {
  border: none !important;
  border-color: transparent !important;
  outline: none !important;
}

/* 覆盖包装元素的边框颜色，但不影响 textarea 本身 */
.chat-input :deep(.n-input-wrapper > *) {
  border-color: transparent !important;
}

.chat-input :deep(.n-input-wrapper > *:not(.n-input__textarea-el)) {
  border-color: transparent !important;
}

/* 强制覆盖所有包装器状态下的边框 */
.chat-input :deep(.n-input-wrapper),
.chat-input :deep(.n-input-wrapper *:not(.n-input__textarea-el)) {
  border-color: transparent !important;
}

.chat-input :deep(.n-input__textarea-el) {
  font-size: var(--font-size-base);
  line-height: 1.7;
  color: var(--text-primary);
  border-radius: var(--radius-xl);
  border: var(--border-width-thin) solid var(--border-color-base) !important;
  border-color: var(--border-color-base) !important;
  transition: all var(--transition-base);
  padding: var(--spacing-md) var(--spacing-lg) !important;
  background: var(--bg-elevated);
  resize: none;
  outline: none !important;
  box-sizing: border-box !important;
  width: 100% !important;
  margin: 0 !important;
  vertical-align: top !important;
  letter-spacing: 0.01em;
}

/* 强制覆盖所有可能的绿色边框（包括验证状态） */
.chat-input :deep(.n-input--success),
.chat-input :deep(.n-input--success *),
.chat-input :deep(.n-input-wrapper--success),
.chat-input :deep(.n-input-wrapper--success *) {
  border-color: transparent !important;
}

.chat-input :deep(.n-input__border--success) {
  border: none !important;
  border-color: transparent !important;
  display: none !important;
}

/* 覆盖所有可能的边框元素（包括聚焦时的绿色边框） */
.chat-input :deep(.n-input__border),
.chat-input :deep(.n-input__state-border),
.chat-input :deep(.n-input__border--focus),
.chat-input :deep(.n-input__border--active),
.chat-input :deep(.n-input__border--hover) {
  border: none !important;
  border-color: transparent !important;
  box-shadow: none !important;
  display: none !important;
}

/* 覆盖聚焦时的包装器边框 */
.chat-input :deep(.n-input-wrapper--focus .n-input__border),
.chat-input :deep(.n-input-wrapper--focus .n-input__state-border) {
  border: none !important;
  border-color: transparent !important;
  box-shadow: none !important;
  display: none !important;
}

/* 覆盖所有可能的绿色 box-shadow（Naive UI 可能使用 box-shadow 作为边框） */
/* 但不影响 textarea 本身 */
.chat-input :deep(.n-input-wrapper),
.chat-input :deep(.n-input-wrapper *:not(.n-input__textarea-el)),
.chat-input :deep(.n-input),
.chat-input :deep(.n-input *:not(.n-input__textarea-el)) {
  box-shadow: none !important;
}

/* 覆盖聚焦时的 box-shadow（但不影响 textarea） */
.chat-input :deep(.n-input-wrapper--focus),
.chat-input :deep(.n-input-wrapper--focus *:not(.n-input__textarea-el)) {
  box-shadow: none !important;
}

/* 覆盖所有可能的伪元素边框 */
.chat-input :deep(.n-input-wrapper::before),
.chat-input :deep(.n-input-wrapper::after),
.chat-input :deep(.n-input-wrapper--focus::before),
.chat-input :deep(.n-input-wrapper--focus::after),
.chat-input :deep(.n-input__border::before),
.chat-input :deep(.n-input__border::after),
.chat-input :deep(.n-input__state-border::before),
.chat-input :deep(.n-input__state-border::after) {
  border: none !important;
  border-color: transparent !important;
  box-shadow: none !important;
  display: none !important;
}

/* 覆盖按钮的验证状态边框 */
.send-button :deep(.n-button--success),
.send-button :deep(.n-button--success *),
.send-button :deep(.n-button__border--success) {
  border: none !important;
  border-color: transparent !important;
  display: none !important;
}

.chat-input :deep(.n-input__textarea-el:focus) {
  border-color: var(--color-primary) !important;
  box-shadow: 0 0 0 3px var(--color-primary-lighter) !important;
  background: var(--bg-elevated);
  outline: none !important;
}

.chat-input :deep(.n-input__textarea-el:focus-visible) {
  outline: none !important;
  border-color: var(--color-primary) !important;
  box-shadow: 0 0 0 4px var(--color-primary-lighter) !important;
}

.chat-input :deep(.n-input__textarea-el::placeholder) {
  color: var(--text-disabled);
  opacity: 1;
  line-height: var(--line-height-relaxed);
}

.send-button {
  height: auto;
  padding: var(--spacing-md) var(--spacing-xl);
  border-radius: var(--radius-xl);
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-secondary) 100%) !important;
  border: none !important;
  border-color: transparent !important;
  font-weight: var(--font-weight-semibold);
  font-size: var(--font-size-base);
  box-shadow: var(--shadow-warm-md);
  transition: all var(--transition-base);
  white-space: nowrap;
  outline: none !important;
  letter-spacing: 0.3px;
}

/* 覆盖所有可能的边框颜色 */
.send-button :deep(*) {
  border-color: transparent !important;
}

.send-button :deep(button) {
  outline: none !important;
  border: none !important;
  border-color: transparent !important;
}

.send-button :deep(.n-button__border),
.send-button :deep(.n-button__state-border),
.send-button :deep(.n-button__border--focus),
.send-button :deep(.n-button__border--hover) {
  border: none !important;
  border-color: transparent !important;
  display: none !important;
}

.send-button :deep(button:focus) {
  outline: none !important;
  box-shadow: 0 4px 18px rgba(255, 182, 193, 0.35) !important;
}

.send-button :deep(button:focus-visible) {
  outline: none !important;
  box-shadow: 0 4px 18px rgba(255, 182, 193, 0.35) !important;
}

.send-button :deep(button:active) {
  outline: none !important;
}

.send-button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: var(--shadow-warm-lg);
}

.send-button:active:not(:disabled) {
  transform: translateY(-1px) scale(0.98);
}

.send-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none !important;
}

.send-button:focus,
.send-button:focus-visible {
  outline: none !important;
  box-shadow: 0 4px 18px rgba(255, 182, 193, 0.35) !important;
}

.send-icon {
  font-size: 18px;
  margin-right: 4px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .chat-layout {
    height: calc(100vh - 160px);
  }

  .sidebar {
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    z-index: 100;
    transform: translateX(0);
    transition: transform 0.3s ease;
  }

  .sidebar-collapsed {
    transform: translateX(-100%);
  }

  .chat-container {
    width: 100%;
    gap: 1rem;
  }
  
  .emotion-card-content {
    flex-direction: column;
    gap: var(--spacing-md);
    align-items: flex-start;
  }
  
  .emotion-left {
    width: 100%;
  }
  
  .config-selectors-inline {
    width: 100%;
    margin-left: 0;
    flex-direction: row;
    align-items: center;
    gap: var(--spacing-xs);
    overflow-x: auto;
    padding-bottom: 4px;
  }
  
  .config-selectors-inline::-webkit-scrollbar {
    height: 4px;
  }
  
  .config-selectors-inline::-webkit-scrollbar-track {
    background: rgba(255, 182, 193, 0.1);
    border-radius: 10px;
  }
  
  .config-selectors-inline::-webkit-scrollbar-thumb {
    background: rgba(255, 182, 193, 0.4);
    border-radius: 10px;
  }
  
  .config-selectors-inline::-webkit-scrollbar-thumb:hover {
    background: rgba(255, 182, 193, 0.6);
  }
  
  .inline-selector {
    min-width: 100px;
    flex-shrink: 0;
  }
  
  .message-bubble {
    max-width: 85%;
    padding: var(--spacing-md) var(--spacing-lg);
  }
  
  .user-message {
    padding-left: var(--spacing-md);
  }
  
  .assistant-message {
    padding-right: var(--spacing-md);
  }
  
  .input-wrapper {
    flex-direction: column;
    gap: 0.75rem;
  }
  
  .send-button {
    width: 100%;
    padding: 12px 20px;
  }
}

@media (max-width: 480px) {
  .emotion-icon-wrapper {
    width: 40px;
    height: 40px;
  }
  
  .emotion-icon {
    font-size: 24px;
  }
  
  .message-bubble {
    max-width: 90%;
    padding: var(--spacing-sm) var(--spacing-md);
    font-size: 14px;
  }
  
  .user-message {
    padding-left: var(--spacing-sm);
  }
  
  .assistant-message {
    padding-right: var(--spacing-sm);
  }
  
  .messages-container {
    padding: var(--spacing-md) var(--spacing-sm);
    gap: var(--spacing-md);
  }
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}
</style>

<style>
/* 全屏样式 - 非 scoped，因为使用 Teleport 渲染到 body */
.card-fullscreen-overlay {
  position: fixed !important;
  top: 0 !important;
  left: 0 !important;
  right: 0 !important;
  bottom: 0 !important;
  width: 100vw !important;
  height: 100vh !important;
  background: rgba(8, 2, 12, 0.85) !important;
  backdrop-filter: blur(16px) !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  padding: 24px !important;
  z-index: 99999 !important;
  overflow: auto !important;
  margin: 0 !important;
  pointer-events: auto !important;
  visibility: visible !important;
  opacity: 1 !important;
}

.card-fullscreen-content {
  position: relative !important;
  width: min(1200px, calc(100vw - 48px)) !important;
  height: min(96vh, calc(100vh - 48px)) !important;
  max-height: calc(100vh - 48px) !important;
  display: flex !important;
  flex-direction: column !important;
  align-items: stretch !important;
  justify-content: flex-start !important;
  padding: clamp(24px, 3vw, 48px) !important;
  border-radius: 32px !important;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.98), rgba(255, 245, 247, 1)) !important;
  border: 1px solid rgba(255, 255, 255, 0.4) !important;
  box-shadow: 0 25px 80px rgba(0, 0, 0, 0.25) !important;
  overflow: hidden !important;
  box-sizing: border-box !important;
  margin: 0 !important;
}

.card-fullscreen-close {
  position: absolute !important;
  top: 24px !important;
  right: 24px !important;
  background: rgba(255, 255, 255, 0.9) !important;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.15) !important;
  z-index: 10 !important;
}

.card-fullscreen-export {
  position: absolute !important;
  top: 24px !important;
  right: 88px !important;
  background: rgba(255, 255, 255, 0.9) !important;
  box-shadow: 0 6px 18px rgba(232, 180, 184, 0.25) !important;
  color: #d9598c !important;
  z-index: 10 !important;
}

.heart-card-fullscreen {
  width: 100% !important;
  flex: 1 !important;
  min-height: 0 !important;
  max-height: 100% !important;
  overflow-y: auto !important;
  overflow-x: hidden !important;
  padding: 0 !important;
  margin: 0 !important;
  border-radius: 24px !important;
  box-sizing: border-box !important;
  position: relative !important;
  z-index: 1 !important;
  display: block !important;
}

/* 覆盖 HeartCard 组件内部的样式，确保在全屏模式下正确显示 */
.heart-card-fullscreen .heart-card {
  width: 100% !important;
  min-height: 100% !important;
  padding: 48px 32px !important;
  margin: 0 !important;
  box-sizing: border-box !important;
  overflow: visible !important;
  display: block !important;
  position: relative !important;
}

/* 确保卡片内容区域可见 */
.heart-card-fullscreen .card-content {
  display: block !important;
  visibility: visible !important;
  opacity: 1 !important;
}

/* 过渡动画 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* 确保过渡期间内容仍然可见 */
.fade-enter-active .card-fullscreen-content,
.fade-leave-active .card-fullscreen-content {
  opacity: 1 !important;
  visibility: visible !important;
}
</style>


