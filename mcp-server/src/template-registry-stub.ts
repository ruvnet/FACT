/**
 * Stub implementation of Template Registry for MCP Server
 */

export class TemplateRegistry {
  private templates: any[] = [
    {
      id: 'financial-analysis',
      name: 'Financial Analysis Template',
      description: 'Analyzes financial data and metrics',
      category: 'finance',
      tags: ['finance', 'analysis']
    },
    {
      id: 'data-processing',
      name: 'Data Processing Template', 
      description: 'Processes and transforms data',
      category: 'data',
      tags: ['data', 'processing']
    }
  ];

  async loadDefaultTemplates() {
    // Templates already loaded in constructor
  }

  async listTemplates(params: any) {
    let filtered = this.templates;
    
    if (params.category) {
      filtered = filtered.filter(t => t.category === params.category);
    }
    
    if (params.tags) {
      filtered = filtered.filter(t => 
        params.tags.some((tag: string) => t.tags.includes(tag))
      );
    }
    
    return filtered;
  }

  async findMatchingTemplates(analysis: any) {
    return this.templates.slice(0, 2); // Return first 2 as suggestions
  }

  async createTemplate(params: any) {
    const template = {
      id: `custom-${Date.now()}`,
      ...params,
      created: new Date().toISOString()
    };
    
    this.templates.push(template);
    return template;
  }
}