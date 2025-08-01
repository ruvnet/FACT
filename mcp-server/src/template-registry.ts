import { logger } from './logger.js';

export interface CognitiveTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  tags: string[];
  pattern: {
    type: string;
    steps: Array<{
      type: string;
      config: any;
    }>;
  };
  cache_ttl?: number;
  created_at: Date;
  updated_at: Date;
}

export class TemplateRegistry {
  private templates: Map<string, CognitiveTemplate> = new Map();

  constructor() {
    this.initializeDefaultTemplates();
  }

  private initializeDefaultTemplates(): void {
    // Add default cognitive templates
    const defaultTemplates: CognitiveTemplate[] = [
      {
        id: 'analysis-basic',
        name: 'Basic Analysis',
        description: 'Simple data analysis and summarization',
        category: 'analysis',
        tags: ['analysis', 'summary', 'basic'],
        pattern: {
          type: 'sequential',
          steps: [
            { type: 'analyze', config: { depth: 'shallow' } },
            { type: 'synthesize', config: { format: 'summary' } },
          ],
        },
        cache_ttl: 3600,
        created_at: new Date(),
        updated_at: new Date(),
      },
      {
        id: 'inquiry-advanced',
        name: 'Advanced Inquiry',
        description: 'Deep inquiry with multi-step reasoning',
        category: 'reasoning',
        tags: ['inquiry', 'reasoning', 'advanced'],
        pattern: {
          type: 'iterative',
          steps: [
            { type: 'analyze', config: { depth: 'deep' } },
            { type: 'transform', config: { mode: 'expand' } },
            { type: 'synthesize', config: { format: 'insights' } },
          ],
        },
        cache_ttl: 7200,
        created_at: new Date(),
        updated_at: new Date(),
      },
      {
        id: 'optimization-solver',
        name: 'Optimization Solver',
        description: 'Constraint-based optimization',
        category: 'optimization',
        tags: ['optimization', 'constraints', 'solver'],
        pattern: {
          type: 'iterative',
          steps: [
            { type: 'analyze', config: { focus: 'constraints' } },
            { type: 'transform', config: { mode: 'optimize' } },
            { type: 'synthesize', config: { format: 'solution' } },
          ],
        },
        cache_ttl: 1800,
        created_at: new Date(),
        updated_at: new Date(),
      },
      {
        id: 'creative-synthesis',
        name: 'Creative Synthesis',
        description: 'Generate creative solutions and ideas',
        category: 'creative',
        tags: ['creative', 'synthesis', 'ideation'],
        pattern: {
          type: 'divergent',
          steps: [
            { type: 'transform', config: { mode: 'diverge' } },
            { type: 'analyze', config: { perspective: 'multiple' } },
            { type: 'synthesize', config: { format: 'creative' } },
          ],
        },
        cache_ttl: 3600,
        created_at: new Date(),
        updated_at: new Date(),
      },
      {
        id: 'decision-support',
        name: 'Decision Support',
        description: 'Multi-criteria decision analysis',
        category: 'decision',
        tags: ['decision', 'analysis', 'support'],
        pattern: {
          type: 'analytical',
          steps: [
            { type: 'analyze', config: { criteria: 'multiple' } },
            { type: 'transform', config: { mode: 'evaluate' } },
            { type: 'synthesize', config: { format: 'recommendation' } },
          ],
        },
        cache_ttl: 3600,
        created_at: new Date(),
        updated_at: new Date(),
      },
    ];

    for (const template of defaultTemplates) {
      this.templates.set(template.id, template);
    }

    logger.info(`Loaded ${defaultTemplates.length} default cognitive templates`);
  }

  async loadDefaultTemplates(): Promise<void> {
    // This could load templates from a file or database
    // For now, we use the initialized templates
    logger.info('Default templates already loaded');
  }

  async getTemplate(id: string): Promise<CognitiveTemplate | undefined> {
    return this.templates.get(id);
  }

  async listTemplates(filters: {
    category?: string;
    tags?: string[];
  }): Promise<CognitiveTemplate[]> {
    let templates = Array.from(this.templates.values());

    if (filters.category) {
      templates = templates.filter(t => t.category === filters.category);
    }

    if (filters.tags && filters.tags.length > 0) {
      templates = templates.filter(t =>
        filters.tags!.some(tag => t.tags.includes(tag))
      );
    }

    return templates;
  }

  async createTemplate(params: {
    name: string;
    description: string;
    pattern: any;
    category?: string;
    tags?: string[];
  }): Promise<CognitiveTemplate> {
    const id = this.generateTemplateId(params.name);
    
    const template: CognitiveTemplate = {
      id,
      name: params.name,
      description: params.description,
      category: params.category || 'custom',
      tags: params.tags || [],
      pattern: params.pattern,
      cache_ttl: 3600, // Default 1 hour
      created_at: new Date(),
      updated_at: new Date(),
    };

    this.templates.set(id, template);
    logger.info(`Created new template: ${id}`);

    return template;
  }

  async updateTemplate(id: string, updates: Partial<CognitiveTemplate>): Promise<CognitiveTemplate | undefined> {
    const template = this.templates.get(id);
    if (!template) {
      return undefined;
    }

    const updated = {
      ...template,
      ...updates,
      id, // Preserve original ID
      updated_at: new Date(),
    };

    this.templates.set(id, updated);
    return updated;
  }

  async deleteTemplate(id: string): Promise<boolean> {
    return this.templates.delete(id);
  }

  async findMatchingTemplates(analysis: any): Promise<CognitiveTemplate[]> {
    const patterns = analysis.patterns || [];
    const complexity = analysis.complexity || 'medium';

    // Find templates that match the patterns
    const matches = Array.from(this.templates.values()).filter(template => {
      // Check if template tags overlap with patterns
      const tagMatch = template.tags.some(tag => 
        patterns.some((p: string) => tag.includes(p) || p.includes(tag))
      );

      // Check complexity compatibility
      const complexityMatch = this.isComplexityCompatible(template, complexity);

      return tagMatch && complexityMatch;
    });

    // Sort by relevance (simple scoring)
    matches.sort((a, b) => {
      const scoreA = this.calculateRelevanceScore(a, patterns);
      const scoreB = this.calculateRelevanceScore(b, patterns);
      return scoreB - scoreA;
    });

    return matches.slice(0, 5); // Return top 5 matches
  }

  private generateTemplateId(name: string): string {
    const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, '-');
    const timestamp = Date.now().toString(36);
    return `${slug}-${timestamp}`;
  }

  private isComplexityCompatible(template: CognitiveTemplate, complexity: string): boolean {
    const templateComplexity = template.pattern.steps.length;
    
    switch (complexity) {
      case 'low':
        return templateComplexity <= 2;
      case 'medium':
        return templateComplexity <= 4;
      case 'high':
        return true; // High complexity can use any template
      default:
        return true;
    }
  }

  private calculateRelevanceScore(template: CognitiveTemplate, patterns: string[]): number {
    let score = 0;

    // Score based on tag matches
    for (const tag of template.tags) {
      for (const pattern of patterns) {
        if (tag.includes(pattern) || pattern.includes(tag)) {
          score += 1;
        }
      }
    }

    // Bonus for exact category match
    if (patterns.includes(template.category)) {
      score += 2;
    }

    return score;
  }
}