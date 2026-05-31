import { defineCollection } from '@nocobase/database';

export default defineCollection({
  name: 'platform_connections',
  title: '平台连接',
  fields: [
    { type: 'string', name: 'platform', title: '平台' },
    { type: 'string', name: 'api_key', title: 'API密钥' },
    { type: 'string', name: 'api_url', title: 'API地址' },
    { type: 'string', name: 'status', title: '状态', defaultValue: 'disconnected' },
    { type: 'string', name: 'account_name', title: '账户名' },
    { type: 'jsonb', name: 'config', title: '配置' },
    { type: 'hasMany', name: 'orders', target: 'external_orders' },
  ],
});
