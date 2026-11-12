import { Activity, BookOpen, Cable, MessagesSquare } from 'lucide-vue-next'

export const workspaceRoutes = [
  { path: '/chat', name: 'chat', title: '对话', icon: MessagesSquare, description: '对话和历史会话将在此接入。' },
  { path: '/knowledge', name: 'knowledge', title: '知识库', icon: BookOpen, description: '文档管理和知识检索将在此接入。' },
  { path: '/aiops', name: 'aiops', title: 'AIOps', icon: Activity, description: '运维分析和任务报告将在此接入。' },
  { path: '/mcp', name: 'mcp', title: 'MCP', icon: Cable, description: '服务连接和工具管理将在此接入。' },
] as const
