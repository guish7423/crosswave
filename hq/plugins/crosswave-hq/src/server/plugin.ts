import { Plugin } from '@nocobase/server';

export class CrossWaveHQPlugin extends Plugin {
  async afterAdd() { }

  async beforeLoad() { }

  async load() {
    await this.db.import({
      directory: __dirname + '/collections',
    });

    this.app.acl.allow('employees', '*');
    this.app.acl.allow('business_lines', '*');
    this.app.acl.allow('external_orders', '*');
    this.app.acl.allow('platform_connections', '*');
  }

  async install() { }

  async afterEnable() { }

  async afterDisable() { }

  async remove() { }
}

export default CrossWaveHQPlugin;
