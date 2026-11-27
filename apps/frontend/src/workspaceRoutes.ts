import { Activity, BookOpen, Cable, MessagesSquare } from 'lucide-vue-next'

export const workspaceRoutes = [
  { path: '/chat', name: 'chat', title: '对话', icon: MessagesSquare, description: '对话和历史会话将在此接入。' },
  { path: '/knowledge', name: 'knowledge', title: '知识库', icon: BookOpen, description: '上传文档并管理索引任务。' },
  { path: '/aiops', name: 'aiops', title: 'AIOps', icon: Activity, description: '告警诊断、实时执行、证据报告与案例。' },
  { path: '/mcp', name: 'mcp', title: 'MCP', icon: Cable, description: '服务连接和工具管理将在此接入。' },
] as const
