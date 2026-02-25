import { defineConfig } from 'vitepress'

// https://vitepress.dev/reference/site-config
export default defineConfig({
  // 通用配置
  title: "Zotero PDF2zh",
  description: "在Zotero中使用PDF2zh和PDF2zh_next进行PDF翻译",
  head: [
    ['link', { rel: 'icon', href: '/favicon.svg' }]
  ],

  // 国际化配置
  locales: {
    root: {
      label: '简体中文',
      lang: 'zh-CN',
      themeConfig: {
        nav: [
          { text: '快速开始', link: '/zh/' },
          { text: '安装', link: '/zh/guide/installation' },
          { text: '配置', link: '/zh/guide/configuration' },
          { text: '常见问题', link: '/zh/guide/faq/' },
          { text: '关于', link: '/zh/about' },
          { text: '贡献指南', link: '/zh/contributing' },
          { text: '赞助', link: '/zh/sponsors' }
        ],

        sidebar: {
          '/zh/guide/': [
            {
              text: '入门',
              items: [
                { text: '安装指南', link: '/zh/guide/installation' },
                { text: 'Docker 部署', link: '/zh/guide/docker' },
                { text: 'Homebrew 部署', link: '/zh/guide/homebrew' }
              ]
            },
            {
              text: '配置',
              items: [
                { text: '基础配置', link: '/zh/guide/configuration' },
                { text: '翻译选项', link: '/zh/guide/translation-options' },
                { text: '额外参数', link: '/zh/guide/extra-params' },
                { text: '包更新', link: '/zh/guide/package-update' }
              ]
            },
            {
              text: '常见问题',
              collapsed: false,
              items: [
                { text: '问题索引', link: '/zh/guide/faq/' },
                { text: '按阶段查找', link: '/zh/guide/faq/by-stage' },
                { text: '虚拟环境', link: '/zh/guide/faq/virtual-env' },
                { text: '网络问题', link: '/zh/guide/faq/network' },
                { text: '环境配置', link: '/zh/guide/faq/environment' },
                { text: '翻译服务', link: '/zh/guide/faq/translation-service' },
                { text: '插件功能', link: '/zh/guide/faq/plugin-features' },
                { text: '有效提问', link: '/zh/guide/faq/asking-questions' }
              ]
            }
          ],
          '/zh/': [
            {
              text: '文档',
              items: [
                { text: '首页', link: '/zh/' },
                { text: '安装指南', link: '/zh/guide/installation' },
                { text: '配置说明', link: '/zh/guide/configuration' },
                { text: '常见问题', link: '/zh/guide/faq/' }
              ]
            },
            {
              text: '项目',
              items: [
                { text: '关于', link: '/zh/about' },
                { text: '贡献指南', link: '/zh/contributing' },
                { text: '赞助', link: '/zh/sponsors' }
              ]
            }
          ]
        },

        footer: {
          message: '基于 MIT 许可发布',
          copyright: 'Copyright © 2024-present Zotero PDF2zh'
        },

        editLink: {
          pattern: 'https://github.com/guaguastandup/zotero-pdf2zh/edit/main/docs/zh/:path',
          text: '在 GitHub 上编辑此页'
        },

        lastUpdated: {
          text: '最后更新',
          formatOptions: {
            dateStyle: 'short',
            timeStyle: 'short'
          }
        },

        outline: {
          label: '页面导航'
        },

        returnToTopLabel: '返回顶部',
        sidebarMenuLabel: '菜单',
        darkModeSwitchLabel: '外观',
        lightModeSwitchTitle: '切换到浅色模式',
        darkModeSwitchTitle: '切换到深色模式'
      }
    },

    en: {
      label: 'English',
      lang: 'en-US',
      title: "Zotero PDF2zh",
      description: "Translate PDFs using PDF2zh and PDF2zh_next in Zotero",
      themeConfig: {
        nav: [
          { text: 'Quick Start', link: '/en/' },
          { text: 'Installation', link: '/en/guide/installation' },
          { text: 'Configuration', link: '/en/guide/configuration' },
          { text: 'FAQ', link: '/en/guide/faq/' },
          { text: 'About', link: '/en/about' },
          { text: 'Contributing', link: '/en/contributing' },
          { text: 'Sponsor', link: '/en/sponsors' }
        ],

        sidebar: {
          '/en/guide/': [
            {
              text: 'Getting Started',
              items: [
                { text: 'Installation', link: '/en/guide/installation' },
                { text: 'Docker Deployment', link: '/en/guide/docker' },
                { text: 'Homebrew Deployment', link: '/en/guide/homebrew' }
              ]
            },
            {
              text: 'Configuration',
              items: [
                { text: 'Basic Configuration', link: '/en/guide/configuration' },
                { text: 'Translation Options', link: '/en/guide/translation-options' },
                { text: 'Extra Parameters', link: '/en/guide/extra-params' },
                { text: 'Package Update', link: '/en/guide/package-update' }
              ]
            },
            {
              text: 'FAQ',
              collapsed: false,
              items: [
                { text: 'Categories', link: '/en/guide/faq/' },
                { text: 'By Stage', link: '/en/guide/faq/by-stage' },
                { text: 'Virtual Environment', link: '/en/guide/faq/virtual-env' },
                { text: 'Network', link: '/en/guide/faq/network' },
                { text: 'Environment', link: '/en/guide/faq/environment' },
                { text: 'Translation Service', link: '/en/guide/faq/translation-service' },
                { text: 'Plugin Features', link: '/en/guide/faq/plugin-features' },
                { text: 'Asking Questions', link: '/en/guide/faq/asking-questions' }
              ]
            }
          ],
          '/en/': [
            {
              text: 'Documentation',
              items: [
                { text: 'Home', link: '/en/' },
                { text: 'Installation', link: '/en/guide/installation' },
                { text: 'Configuration', link: '/en/guide/configuration' },
                { text: 'FAQ', link: '/en/guide/faq/' }
              ]
            },
            {
              text: 'Project',
              items: [
                { text: 'About', link: '/en/about' },
                { text: 'Contributing', link: '/en/contributing' },
                { text: 'Sponsor', link: '/en/sponsors' }
              ]
            }
          ]
        },

        footer: {
          message: 'Released under MIT License',
          copyright: 'Copyright © 2024-present Zotero PDF2zh'
        },

        editLink: {
          pattern: 'https://github.com/guaguastandup/zotero-pdf2zh/edit/main/docs/en/:path',
          text: 'Edit this page on GitHub'
        },

        lastUpdated: {
          text: 'Last Updated',
          formatOptions: {
            dateStyle: 'short',
            timeStyle: 'short'
          }
        },

        outline: {
          label: 'On this page'
        },

        returnToTopLabel: 'Return to top',
        sidebarMenuLabel: 'Menu',
        darkModeSwitchLabel: 'Appearance',
        lightModeSwitchTitle: 'Switch to light mode',
        darkModeSwitchTitle: 'Switch to dark mode'
      }
    }
  },

  themeConfig: {
    // 跨语言共享的配置
    socialLinks: [
      { icon: 'github', link: 'https://github.com/guaguastandup/zotero-pdf2zh' }
    ],

    search: {
      provider: 'local'
    }
  }
})
