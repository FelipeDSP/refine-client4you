import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { usePageTitle } from "@/contexts/PageTitleContext";
import { apiGet, apiPut } from "@/lib/api";
import { usePlanPermissions } from "@/hooks/usePlanPermissions";
import { PlanBlockedOverlay } from "@/components/PlanBlockedOverlay";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Slider } from "@/components/ui/slider";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { 
  Bot, 
  Zap, 
  Settings2, 
  MessageSquare, 
  Brain, 
  Sparkles,
  Save,
  Loader2,
  Info,
  Clock,
  Target,
  Shield,
  Lightbulb,
  AlertCircle,
  Settings,
  ExternalLink
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface AgentConfig {
  enabled: boolean;
  name: string;
  personality: string;
  systemPrompt: string;
  welcomeMessage: string;
  responseDelay: number;
  maxResponseLength: number;
  tone: 'formal' | 'casual' | 'professional' | 'friendly';
  language: 'pt-BR' | 'en-US' | 'es-ES';
  model: string;
  temperature: number;
  openaiApiKey: string;
  autoQualify: boolean;
  qualificationQuestions: string[];
  blockedTopics: string[];
  workingHours: {
    enabled: boolean;
    start: string;
    end: string;
    timezone: string;
  };
}

const DEFAULT_CONFIG: AgentConfig = {
  enabled: false,
  name: "Assistente Virtual",
  personality: "Sou um assistente virtual prestativo e profissional.",
  systemPrompt: `Você é um assistente virtual de atendimento ao cliente.

Suas principais responsabilidades:
- Responder dúvidas sobre produtos e serviços
- Qualificar leads interessados
- Agendar reuniões quando solicitado
- Direcionar para atendimento humano quando necessário

Regras importantes:
- Seja sempre cordial e profissional
- Não invente informações que não possui
- Colete nome, email e telefone quando apropriado
- Pergunte como pode ajudar se a mensagem for vaga`,
  welcomeMessage: "Olá! 👋 Sou o assistente virtual da empresa. Como posso ajudar você hoje?",
  responseDelay: 3,
  maxResponseLength: 500,
  tone: 'professional',
  language: 'pt-BR',
  model: 'gpt-4.1-mini',
  temperature: 0.7,
  openaiApiKey: '',
  autoQualify: true,
  qualificationQuestions: [
    "Qual é o seu nome?",
    "Qual é o seu email para contato?",
    "Como conheceu nossa empresa?"
  ],
  blockedTopics: [],
  workingHours: {
    enabled: false,
    start: "09:00",
    end: "18:00",
    timezone: "America/Sao_Paulo"
  }
};

export default function AgenteIA() {
  const { setPageTitle } = usePageTitle();
  const { permissions, isLoading: isLoadingPermissions } = usePlanPermissions();
  const { toast } = useToast();
  
  const [config, setConfig] = useState<AgentConfig>(DEFAULT_CONFIG);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoadingConfig, setIsLoadingConfig] = useState(true);
  const [hasChanges, setHasChanges] = useState(false);
  const [hasOpenaiKey, setHasOpenaiKey] = useState(false);

  const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

  useEffect(() => {
    setPageTitle("Agente IA", Bot);
  }, [setPageTitle]);

  // Carregar configurações do backend
  const loadConfig = useCallback(async () => {
    try {
      setIsLoadingConfig(true);
      const response = await apiGet(`${BACKEND_URL}/api/agent/config`);
      if (response.ok) {
        const data = await response.json();
        if (data.config) {
          // Verificar se tem API key configurada
          setHasOpenaiKey(!!data.config.openai_api_key);
          
          // Mapear campos do banco para o frontend
          setConfig({
            enabled: data.config.enabled ?? false,
            name: data.config.name ?? DEFAULT_CONFIG.name,
            personality: data.config.personality ?? DEFAULT_CONFIG.personality,
            systemPrompt: data.config.system_prompt ?? DEFAULT_CONFIG.systemPrompt,
            welcomeMessage: data.config.welcome_message ?? DEFAULT_CONFIG.welcomeMessage,
            responseDelay: data.config.response_delay ?? DEFAULT_CONFIG.responseDelay,
            maxResponseLength: data.config.max_response_length ?? DEFAULT_CONFIG.maxResponseLength,
            tone: data.config.tone ?? DEFAULT_CONFIG.tone,
            language: data.config.language ?? DEFAULT_CONFIG.language,
            model: data.config.model ?? DEFAULT_CONFIG.model,
            temperature: data.config.temperature ?? DEFAULT_CONFIG.temperature,
            openaiApiKey: data.config.openai_api_key ?? DEFAULT_CONFIG.openaiApiKey,
            autoQualify: data.config.auto_qualify ?? DEFAULT_CONFIG.autoQualify,
            qualificationQuestions: data.config.qualification_questions ?? DEFAULT_CONFIG.qualificationQuestions,
            blockedTopics: data.config.blocked_topics ?? DEFAULT_CONFIG.blockedTopics,
            workingHours: data.config.working_hours ?? DEFAULT_CONFIG.workingHours,
          });
        }
      }
    } catch (error) {
      console.error('Error loading agent config:', error);
      // Fallback: tentar localStorage
      const saved = localStorage.getItem('agentConfig');
      if (saved) {
        try { setConfig(JSON.parse(saved)); } catch (e) {}
      }
    } finally {
      setIsLoadingConfig(false);
    }
  }, [BACKEND_URL]);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      // Mapear campos do frontend para o backend
      const payload = {
        enabled: config.enabled,
        name: config.name,
        personality: config.personality,
        system_prompt: config.systemPrompt,
        welcome_message: config.welcomeMessage,
        response_delay: config.responseDelay,
        max_response_length: config.maxResponseLength,
        tone: config.tone,
        language: config.language,
        model: config.model,
        temperature: config.temperature,
        openai_api_key: config.openaiApiKey,
        auto_qualify: config.autoQualify,
        qualification_questions: config.qualificationQuestions,
        blocked_topics: config.blockedTopics,
        working_hours: config.workingHours,
      };

      const response = await apiPut(`${BACKEND_URL}/api/agent/config`, payload);
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Erro ao salvar');
      }

      // Backup em localStorage
      localStorage.setItem('agentConfig', JSON.stringify(config));
      
      toast({
        title: "Configurações salvas!",
        description: "As configurações do agente foram atualizadas no servidor.",
      });
      setHasChanges(false);
    } catch (error: any) {
      toast({
        variant: "destructive",
        title: "Erro ao salvar",
        description: error.message || "Não foi possível salvar as configurações.",
      });
    } finally {
      setIsSaving(false);
    }
  };

  const updateConfig = <K extends keyof AgentConfig>(key: K, value: AgentConfig[K]) => {
    setConfig(prev => ({ ...prev, [key]: value }));
    setHasChanges(true);
  };

  // Loading
  if (isLoadingPermissions || isLoadingConfig) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-purple-600" />
      </div>
    );
  }

  // Verificar se conta está suspensa
  if (permissions.isSuspended) {
    return (
      <PlanBlockedOverlay
        feature="agente"
        currentPlan={permissions.planName}
        requiredPlan="avancado"
        isSuspended={true}
      />
    );
  }

  // Verificar se plano expirou
  if (permissions.isPlanExpired) {
    return (
      <PlanBlockedOverlay
        feature="agente"
        currentPlan={permissions.planName}
        requiredPlan="avancado"
        isExpired={true}
        expiresAt={permissions.expiresAt}
      />
    );
  }

  // Verificar se tem permissão
  if (!permissions.canUseAgenteIA) {
    return (
      <PlanBlockedOverlay
        feature="agente"
        currentPlan={permissions.planName}
        requiredPlan="avancado"
      />
    );
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-10 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-3xl font-bold tracking-tight text-slate-900">Agente IA</h2>
            <Badge className="bg-purple-600 text-white">Beta</Badge>
          </div>
          <p className="text-muted-foreground mt-1">
            Configure seu assistente virtual inteligente para WhatsApp
          </p>
        </div>
        
        <div className="flex items-center gap-3">
          {hasChanges && (
            <Badge variant="outline" className="text-orange-600 border-orange-200">
              Alterações não salvas
            </Badge>
          )}
          <Button 
            onClick={handleSave} 
            disabled={isSaving || !hasChanges}
            className="gap-2 bg-purple-600 hover:bg-purple-700"
          >
            {isSaving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            Salvar Configurações
          </Button>
        </div>
      </div>

      {/* Alerta de API Key não configurada */}
      {!isLoadingConfig && !hasOpenaiKey && (
        <Alert className="border-orange-200 bg-orange-50">
          <AlertCircle className="h-5 w-5 text-orange-600" />
          <AlertTitle className="text-orange-800">Configuração necessária</AlertTitle>
          <AlertDescription className="text-orange-700">
            <p className="mb-3">
              Para o Agente IA funcionar, você precisa configurar sua chave da API OpenAI.
            </p>
            <Link to="/configuracoes?tab=integrations">
              <Button variant="outline" size="sm" className="gap-2 border-orange-300 hover:bg-orange-100">
                <Settings className="h-4 w-4" />
                Ir para Configurações
                <ExternalLink className="h-3 w-3" />
              </Button>
            </Link>
          </AlertDescription>
        </Alert>
      )}

      {/* Status Card */}
      <Card className={`border-2 ${config.enabled ? 'border-green-200 bg-green-50/50' : 'border-slate-200'}`}>
        <CardContent className="flex items-center justify-between p-6">
          <div className="flex items-center gap-4">
            <div className={`p-3 rounded-full ${config.enabled ? 'bg-green-100' : 'bg-slate-100'}`}>
              <Bot className={`h-6 w-6 ${config.enabled ? 'text-green-600' : 'text-slate-400'}`} />
            </div>
            <div>
              <h3 className="font-semibold text-lg">
                Agente {config.enabled ? 'Ativo' : 'Desativado'}
              </h3>
              <p className="text-sm text-muted-foreground">
                {config.enabled 
                  ? 'O agente está respondendo mensagens automaticamente' 
                  : 'Ative para começar a responder automaticamente'}
              </p>
            </div>
          </div>
          
          <Switch
            checked={config.enabled}
            onCheckedChange={(checked) => updateConfig('enabled', checked)}
            className="scale-125"
          />
        </CardContent>
      </Card>

      {/* Info de Integração */}
      <Card className="border-blue-200 bg-blue-50/50">
        <CardContent className="flex items-start gap-4 p-4">
          <Info className="h-5 w-5 text-blue-600 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-sm font-medium text-blue-800">Integração Ativa</p>
            <p className="text-sm text-blue-700 mt-1">
              O Agente IA está integrado com n8n. Configure os parâmetros abaixo 
              e ative o agente para começar a responder automaticamente via WhatsApp.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Tabs de Configuração */}
      <Tabs defaultValue="personality" className="space-y-6">
        <TabsList className="grid w-full grid-cols-4 lg:w-auto lg:inline-flex">
          <TabsTrigger value="personality" className="gap-2">
            <Brain className="h-4 w-4" />
            <span className="hidden sm:inline">Personalidade</span>
          </TabsTrigger>
          <TabsTrigger value="prompts" className="gap-2">
            <MessageSquare className="h-4 w-4" />
            <span className="hidden sm:inline">Prompts</span>
          </TabsTrigger>
          <TabsTrigger value="behavior" className="gap-2">
            <Settings2 className="h-4 w-4" />
            <span className="hidden sm:inline">Comportamento</span>
          </TabsTrigger>
          <TabsTrigger value="qualification" className="gap-2">
            <Target className="h-4 w-4" />
            <span className="hidden sm:inline">Qualificação</span>
          </TabsTrigger>
        </TabsList>

        {/* Tab: Personalidade */}
        <TabsContent value="personality" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-purple-600" />
                Identidade do Agente
              </CardTitle>
              <CardDescription>
                Defina como seu agente se apresenta e interage
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="name">Nome do Agente</Label>
                  <Input
                    id="name"
                    value={config.name}
                    onChange={(e) => updateConfig('name', e.target.value)}
                    placeholder="Ex: Sofia, Assistente Virtual"
                  />
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="tone">Tom de Comunicação</Label>
                  <Select 
                    value={config.tone} 
                    onValueChange={(value: AgentConfig['tone']) => updateConfig('tone', value)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="formal">Formal</SelectItem>
                      <SelectItem value="professional">Profissional</SelectItem>
                      <SelectItem value="friendly">Amigável</SelectItem>
                      <SelectItem value="casual">Casual</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="personality">Descrição da Personalidade</Label>
                <Textarea
                  id="personality"
                  value={config.personality}
                  onChange={(e) => updateConfig('personality', e.target.value)}
                  placeholder="Descreva como o agente deve se comportar..."
                  rows={3}
                />
                <p className="text-xs text-muted-foreground">
                  Uma breve descrição de como o agente deve se apresentar e agir
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="welcome">Mensagem de Boas-vindas</Label>
                <Textarea
                  id="welcome"
                  value={config.welcomeMessage}
                  onChange={(e) => updateConfig('welcomeMessage', e.target.value)}
                  placeholder="Primeira mensagem enviada ao contato..."
                  rows={2}
                />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tab: Prompts */}
        <TabsContent value="prompts" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Brain className="h-5 w-5 text-purple-600" />
                Prompt do Sistema
              </CardTitle>
              <CardDescription>
                Instruções detalhadas de como o agente deve se comportar
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="systemPrompt">Instruções do Agente</Label>
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger>
                        <Info className="h-4 w-4 text-muted-foreground" />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-sm">
                        <p>Este prompt é enviado ao modelo de IA antes de cada conversa. 
                        Define o contexto, regras e comportamento do agente.</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
                <Textarea
                  id="systemPrompt"
                  value={config.systemPrompt}
                  onChange={(e) => updateConfig('systemPrompt', e.target.value)}
                  placeholder="Defina as instruções detalhadas..."
                  rows={12}
                  className="font-mono text-sm"
                />
              </div>

              <div className="bg-slate-50 p-4 rounded-lg border">
                <div className="flex items-start gap-3">
                  <Lightbulb className="h-5 w-5 text-amber-500 mt-0.5" />
                  <div className="text-sm">
                    <p className="font-medium text-slate-700">Dicas para um bom prompt:</p>
                    <ul className="mt-2 space-y-1 text-slate-600">
                      <li>• Defina claramente o papel do agente</li>
                      <li>• Liste as principais responsabilidades</li>
                      <li>• Estabeleça regras e limitações</li>
                      <li>• Indique quando transferir para humano</li>
                      <li>• Especifique informações a coletar</li>
                    </ul>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tab: Comportamento */}
        <TabsContent value="behavior" className="space-y-6">
          {/* Aviso de configuração OpenAI */}
          {!hasOpenaiKey && (
            <Card className="border-orange-200 bg-orange-50">
              <CardContent className="flex items-center justify-between p-4">
                <div className="flex items-center gap-3">
                  <Brain className="h-5 w-5 text-orange-600" />
                  <div>
                    <p className="font-medium text-orange-800">Configure sua API Key da OpenAI</p>
                    <p className="text-sm text-orange-700">Necessário para o agente funcionar</p>
                  </div>
                </div>
                <Link to="/configuracoes?tab=integrations">
                  <Button variant="outline" size="sm" className="border-orange-300 hover:bg-orange-100">
                    Configurar
                  </Button>
                </Link>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Clock className="h-5 w-5 text-purple-600" />
                Configurações de Resposta
              </CardTitle>
              <CardDescription>
                Ajuste o tempo e formato das respostas
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-4">
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <Label>Delay de Resposta: {config.responseDelay}s</Label>
                    <span className="text-sm text-muted-foreground">
                      Simula tempo de digitação
                    </span>
                  </div>
                  <Slider
                    value={[config.responseDelay]}
                    onValueChange={([value]) => updateConfig('responseDelay', value)}
                    min={1}
                    max={10}
                    step={1}
                    className="w-full"
                  />
                  <p className="text-xs text-muted-foreground">
                    Aguarda alguns segundos antes de responder para parecer mais natural
                  </p>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <Label>Tamanho Máximo: {config.maxResponseLength} caracteres</Label>
                  </div>
                  <Slider
                    value={[config.maxResponseLength]}
                    onValueChange={([value]) => updateConfig('maxResponseLength', value)}
                    min={100}
                    max={1000}
                    step={50}
                    className="w-full"
                  />
                </div>
              </div>

              <div className="border-t pt-6">
                <h4 className="font-medium mb-4 flex items-center gap-2">
                  <Clock className="h-4 w-4" />
                  Horário de Funcionamento
                </h4>
                
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <p className="font-medium">Limitar horário</p>
                    <p className="text-sm text-muted-foreground">
                      Agente só responde em horário comercial
                    </p>
                  </div>
                  <Switch
                    checked={config.workingHours.enabled}
                    onCheckedChange={(checked) => updateConfig('workingHours', {
                      ...config.workingHours,
                      enabled: checked
                    })}
                  />
                </div>

                {config.workingHours.enabled && (
                  <div className="grid gap-4 sm:grid-cols-2 p-4 bg-slate-50 rounded-lg">
                    <div className="space-y-2">
                      <Label>Início</Label>
                      <Input
                        type="time"
                        value={config.workingHours.start}
                        onChange={(e) => updateConfig('workingHours', {
                          ...config.workingHours,
                          start: e.target.value
                        })}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Fim</Label>
                      <Input
                        type="time"
                        value={config.workingHours.end}
                        onChange={(e) => updateConfig('workingHours', {
                          ...config.workingHours,
                          end: e.target.value
                        })}
                      />
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tab: Qualificação */}
        <TabsContent value="qualification" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Target className="h-5 w-5 text-purple-600" />
                Qualificação Automática
              </CardTitle>
              <CardDescription>
                Configure como o agente qualifica leads
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Qualificação Automática</p>
                  <p className="text-sm text-muted-foreground">
                    Agente coleta informações do lead durante a conversa
                  </p>
                </div>
                <Switch
                  checked={config.autoQualify}
                  onCheckedChange={(checked) => updateConfig('autoQualify', checked)}
                />
              </div>

              {config.autoQualify && (
                <div className="space-y-3 p-4 bg-slate-50 rounded-lg">
                  <Label>Perguntas de Qualificação</Label>
                  <Textarea
                    value={config.qualificationQuestions.join('\n')}
                    onChange={(e) => updateConfig('qualificationQuestions', 
                      e.target.value.split('\n').filter(q => q.trim())
                    )}
                    placeholder="Uma pergunta por linha..."
                    rows={4}
                  />
                  <p className="text-xs text-muted-foreground">
                    O agente tentará coletar essas informações naturalmente durante a conversa
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Shield className="h-5 w-5 text-purple-600" />
                Tópicos Bloqueados
              </CardTitle>
              <CardDescription>
                Assuntos que o agente não deve discutir
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Textarea
                value={config.blockedTopics.join('\n')}
                onChange={(e) => updateConfig('blockedTopics', 
                  e.target.value.split('\n').filter(t => t.trim())
                )}
                placeholder="Um tópico por linha (ex: preços, concorrentes, política)..."
                rows={4}
              />
              <p className="text-xs text-muted-foreground mt-2">
                O agente direcionará para atendimento humano quando esses tópicos surgirem
              </p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
