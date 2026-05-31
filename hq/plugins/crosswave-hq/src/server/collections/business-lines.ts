import { defineCollection } from '@nocobase/database';

export default defineCollection({
  name: 'business_lines',
  title: '业务线',
  fields: [
    { type: 'string', name: 'name', title: '名称' },
    { type: 'string', name: 'slug', title: '标识' },
    { type: 'string', name: 'status', title: '状态', defaultValue: 'active' },
    { type: 'float', name: 'monthly_revenue', title: '月收入', defaultValue: 0 },
    { type: 'integer', name: 'customer_count', title: '客户数', defaultValue: 0 },
    { type: 'jsonb', name: 'health_metrics', title: '健康指标' },
    { type: 'hasMany', name: 'employees', target: 'employees' },
    { type: 'hasMany', name: 'orders', target: 'external_orders' },
  ],
});
