import DefaultTheme from 'vitepress/theme'
import Layout from './Layout.vue'

// 注意：vitepress-plugin-tabs 0.7.3+ 版本不再需要手动导入 CSS
// 如果标签页样式有问题，可能需要检查插件版本

export default {
  extends: DefaultTheme,
  Layout
}
