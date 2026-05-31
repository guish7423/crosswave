import { defineCollection } from '@nocobase/database';

export default defineCollection({
  name: 'external_orders',
  title: '外部订单',
  fields: [
    { type: 'string', name: 'title', title: '标题' },
    { type: 'string', name: 'platform', title: '来源平台' },
    { type: 'string', name: 'status', title: '状态', defaultValue: 'pending' },
    { type: 'float', name: 'budget', title: '预算' },
    { type: 'string', name: 'currency', title: '币种', defaultValue: 'USD' },
    { type: 'text', name: 'description', title: '描述' },
    { type: 'string', name: 'external_id', title: '外部ID' },
    { type: 'float', name: 'score', title: '评分', defaultValue: 0 },
    { type: 'jsonb', name: 'metadata', title: '元数据' },
    { type: 'belongsTo', name: 'business_line', target: 'business_lines' },
    { type: 'belongsTo', name: 'assignee', target: 'employees' },
  ],
});
