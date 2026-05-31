import { defineCollection } from '@nocobase/database';

export default defineCollection({
  name: 'employees',
  title: '员工',
  fields: [
    { type: 'string', name: 'name', title: '姓名' },
    { type: 'string', name: 'type', title: '类型', defaultValue: 'ai' },
    { type: 'string', name: 'role', title: '角色' },
    { type: 'string', name: 'status', title: '状态', defaultValue: 'idle' },
    { type: 'integer', name: 'performance_score', title: '绩效分' },
    { type: 'jsonb', name: 'metadata', title: '元数据' },
    { type: 'belongsToMany', name: 'business_lines', target: 'business_lines' },
  ],
});
