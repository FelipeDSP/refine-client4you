import { useState, useEffect } from "react";
import { Rocket, Users, Loader2, Check, MessageSquare, Clock, Calendar, Globe, Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Lead } from "@/types";
import { useCampaigns } from "@/hooks/useCampaigns";
import { usePlanPermissions } from "@/hooks/usePlanPermissions";
import { useCompanySettings } from "@/hooks/useCompanySettings";
import { toast } from "@/hooks/use-toast";
import { QuotaLimitModal } from "./QuotaLimitModal";

interface CreateCampaignFromLeadsProps {
  leads: Lead[];
  selectedLeads?: string[];
}

const DAYS_OF_WEEK = [
  { value: "0", label: "D", fullName: "Domingo" },
  { value: "1", label: "S", fullName: "Segunda" },
  { value: "2", label: "T", fullName: "Terça" },
  { value: "3", label: "Q", fullName: "Quarta" },
  { value: "4", label: "Q", fullName: "Quinta" },
  { value: "5", label: "S", fullName: "Sexta" },
  { value: "6", label: "S", fullName: "Sábado" },
];

const TIMEZONES = [
  { value: "America/Sao_Paulo", label: "Brasília", offset: "-03:00" },
  { value: "America/Manaus", label: "Amazonas", offset: "-04:00" },
  { value: "America/Rio_Branco", label: "Acre", offset: "-05:00" },
  { value: "America/Cuiaba", label: "Mato Grosso", offset: "-04:00" },
  { value: "America/Noronha", label: "Fernando de Noronha", offset: "-02:00" },
  { value: "America/Fortaleza", label: "Nordeste", offset: "-03:00" },
];

const PRESET_SCHEDULES = [
  { label: "Horário Comercial", start: "08:00", end: "18:00", days: ["1", "2", "3", "4", "5"] },
  { label: "Manhã", start: "08:00", end: "12:00", days: ["1", "2", "3", "4", "5"] },
  { label: "Tarde", start: "13:00", end: "18:00", days: ["1", "2", "3", "4", "5"] },
  { label: "Dia Inteiro", start: "08:00", end: "21:00", days: ["1", "2", "3", "4", "5"] },
];

export function CreateCampaignFromLeads({ leads, selectedLeads = [] }: CreateCampaignFromLeadsProps) {
  const [open, setOpen] = useState(false);
  const [showUpgradeModal, setShowUpgradeModal] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  
  const { permissions } = usePlanPermissions();
  const { createCampaignFromLeads } = useCampaigns();
  const { settings } = useCompanySettings();
  
  // Formulário
  const [name, setName] = useState("");
  const [messageText, setMessageText] = useState("");
  const [intervalMin, setIntervalMin] = useState(30);
  const [intervalMax, setIntervalMax] = useState(120);
  const [timezone, setTimezone] = useState("America/Sao_Paulo");
  const [startTime, setStartTime] = useState("08:00");
  const [endTime, setEndTime] = useState("18:00");
  const [workingDays, setWorkingDays] = useState<string[]>(["1", "2", "3", "4", "5"]);
  const [dailyLimit, setDailyLimit] = useState(300);

  // Carregar timezone das configurações
  useEffect(() => {
    if (settings?.timezone) {
      setTimezone(settings.timezone);
    }
  }, [settings]);

  // Calcular leads a usar
  const leadsToUse = selectedLeads.length > 0 
    ? leads.filter(l => selectedLeads.includes(l.id))
    : leads;
  
  // Filtrar apenas leads com WhatsApp
  const leadsWithWhatsApp = leadsToUse.filter(l => l.hasWhatsApp && l.phone);

  const handleOpenDialog = () => {
    // Verificar se tem permissão para usar disparador
    if (!permissions.canUseDisparador) {
      setShowUpgradeModal(true);
      return;
    }
    
    if (leadsWithWhatsApp.length === 0) {
      toast({
        title: "Sem leads com WhatsApp",
        description: "Selecione leads que tenham WhatsApp validado para criar a campanha.",
        variant: "destructive",
      });
      return;
    }
    
    setOpen(true);
  };

  const applyPreset = (preset: typeof PRESET_SCHEDULES[0]) => {
    setStartTime(preset.start);
    setEndTime(preset.end);
    setWorkingDays(preset.days);
    toast({
      title: `Preset aplicado: ${preset.label}`,
      description: `${preset.start} - ${preset.end}`,
    });
  };

  const handleCreate = async () => {
    if (!name.trim()) {
      toast({ title: "Erro", description: "Nome da campanha é obrigatório.", variant: "destructive" });
      return;
    }
    if (!messageText.trim()) {
      toast({ title: "Erro", description: "Mensagem é obrigatória.", variant: "destructive" });
      return;
    }
    if (workingDays.length === 0) {
      toast({ title: "Erro", description: "Selecione pelo menos um dia de funcionamento.", variant: "destructive" });
      return;
    }
    if (startTime >= endTime) {
      toast({ title: "Erro", description: "O horário de início deve ser anterior ao de término.", variant: "destructive" });
      return;
    }

    setIsCreating(true);
    
    try {
      // Preparar contatos
      const contacts = leadsWithWhatsApp.map(lead => ({
        name: lead.name,
        phone: lead.phone!,
        category: lead.category || "",
        extra_data: {
          address: lead.address,
          website: lead.website,
          rating: lead.rating,
        }
      }));

      // Criar campanha
      await createCampaignFromLeads({
        name: name.trim(),
        message: {
          type: "text",
          text: messageText,
        },
        settings: {
          interval_min: Math.floor(Number(intervalMin)),
          interval_max: Math.floor(Number(intervalMax)),
          start_time: startTime,
          end_time: endTime,
          daily_limit: dailyLimit,
          working_days: workingDays.map(d => parseInt(d, 10)),
          timezone: timezone,
        },
        contacts: contacts,
      });

      toast({
        title: "Campanha Criada!",
        description: `${contacts.length} contatos adicionados. Acesse o Disparador para iniciar.`,
        className: "bg-green-500 text-white",
      });

      setOpen(false);
      resetForm();
      
    } catch (error: any) {
      console.error("Erro ao criar campanha:", error);
      toast({
        title: "Erro",
        description: error.message || "Não foi possível criar a campanha.",
        variant: "destructive",
      });
    } finally {
      setIsCreating(false);
    }
  };

  const resetForm = () => {
    setName("");
    setMessageText("");
    setWorkingDays(["1", "2", "3", "4", "5"]);
    setStartTime("08:00");
    setEndTime("18:00");
    setIntervalMin(30);
    setIntervalMax(120);
  };

  // Estimativas
  const avgInterval = (intervalMin + intervalMax) / 2;
  const [sh, sm] = startTime.split(':').map(Number);
  const [eh, em] = endTime.split(':').map(Number);
  const hoursPerDay = Math.max(0, (eh * 60 + em - sh * 60 - sm) / 60);
  const messagesPerHour = Math.floor(3600 / avgInterval);
  const daysToComplete = Math.ceil(leadsWithWhatsApp.length / Math.min(dailyLimit, messagesPerHour * hoursPerDay)) || 1;

  return (
    <>
      <Button 
        variant="default"
        size="sm" 
        onClick={handleOpenDialog}
        className="gap-2 bg-[#F59600] hover:bg-[#e08900] text-white"
        disabled={leadsToUse.length === 0}
      >
        <Rocket className="h-4 w-4" />
        Criar Campanha
        {selectedLeads.length > 0 && (
          <Badge variant="secondary" className="ml-1 bg-white/20 text-white">
            {leadsWithWhatsApp.length}
          </Badge>
        )}
      </Button>

      <QuotaLimitModal open={showUpgradeModal} onOpenChange={setShowUpgradeModal} />

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-xl font-bold text-slate-800">
              <Rocket className="h-5 w-5 text-[#F59600]" />
              Nova Campanha dos Leads
            </DialogTitle>
            <DialogDescription>
              Configure e envie mensagens para os leads selecionados.
            </DialogDescription>
          </DialogHeader>

          {/* Resumo dos Leads */}
          <Card className="bg-blue-50/50 border-blue-100 my-2">
            <CardContent className="py-3 px-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-100 rounded-lg">
                  <Users className="h-5 w-5 text-blue-600" />
                </div>
                <div>
                  <p className="font-semibold text-blue-900">
                    {leadsWithWhatsApp.length} contatos prontos para envio
                  </p>
                  {leadsToUse.length > leadsWithWhatsApp.length && (
                    <p className="text-xs text-blue-700">
                      ({leadsToUse.length - leadsWithWhatsApp.length} leads sem WhatsApp ignorados)
                    </p>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          <Tabs defaultValue="message" className="w-full mt-2">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="message" className="flex items-center gap-2">
                <MessageSquare className="h-4 w-4" /> Mensagem
              </TabsTrigger>
              <TabsTrigger value="settings" className="flex items-center gap-2">
                <Clock className="h-4 w-4" /> Agendamento
              </TabsTrigger>
            </TabsList>

            {/* ABA: MENSAGEM */}
            <TabsContent value="message" className="space-y-4 pt-4">
              <div className="space-y-2">
                <Label htmlFor="name">Nome da Campanha</Label>
                <Input 
                  id="name" 
                  value={name} 
                  onChange={(e) => setName(e.target.value)} 
                  placeholder="Ex: Oferta Especial Janeiro"
                  className="font-medium"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="message">Conteúdo da Mensagem</Label>
                <Textarea 
                  id="message" 
                  value={messageText} 
                  onChange={(e) => setMessageText(e.target.value)} 
                  placeholder="Olá {Nome}, tudo bem? Temos uma oferta..." 
                  className="h-32 resize-none"
                />
                <div className="flex gap-2">
                  <Badge variant="outline" className="cursor-pointer hover:bg-slate-100" onClick={() => setMessageText(prev => prev + " {Nome}")}>
                    {`{Nome}`}
                  </Badge>
                  <Badge variant="outline" className="cursor-pointer hover:bg-slate-100" onClick={() => setMessageText(prev => prev + " {Empresa}")}>
                    {`{Empresa}`}
                  </Badge>
                </div>
              </div>
            </TabsContent>

            {/* ABA: CONFIGURAÇÕES / AGENDAMENTO */}
            <TabsContent value="settings" className="space-y-5 pt-4">
              
              {/* Fuso Horário e Presets */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="flex items-center gap-2">
                    <Globe className="h-4 w-4" /> Fuso Horário
                  </Label>
                  <Select value={timezone} onValueChange={setTimezone}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {TIMEZONES.map((tz) => (
                        <SelectItem key={tz.value} value={tz.value}>
                          {tz.label} ({tz.offset})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Atalhos de Horário</Label>
                  <Select onValueChange={(v) => applyPreset(PRESET_SCHEDULES[parseInt(v)])}>
                    <SelectTrigger>
                      <SelectValue placeholder="Aplicar Preset..." />
                    </SelectTrigger>
                    <SelectContent>
                      {PRESET_SCHEDULES.map((preset, idx) => (
                        <SelectItem key={idx} value={String(idx)}>
                          {preset.label} ({preset.start}-{preset.end})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Horários */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="text-sm">Início</Label>
                  <Input 
                    type="time" 
                    value={startTime} 
                    onChange={(e) => setStartTime(e.target.value)}
                    className="font-mono"
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-sm">Término</Label>
                  <Input 
                    type="time" 
                    value={endTime} 
                    onChange={(e) => setEndTime(e.target.value)}
                    className="font-mono"
                  />
                </div>
              </div>

              {/* Dias da Semana */}
              <div className="space-y-2">
                <Label className="flex items-center gap-2">
                  <Calendar className="h-4 w-4" /> Dias de Envio
                </Label>
                <ToggleGroup type="multiple" value={workingDays} onValueChange={setWorkingDays} className="justify-start gap-1">
                  {DAYS_OF_WEEK.map((day) => (
                    <TooltipProvider key={day.value}>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <ToggleGroupItem 
                            value={day.value}
                            className="h-10 w-10 rounded-full border data-[state=on]:bg-[#054173] data-[state=on]:text-white data-[state=on]:border-[#054173] shadow-sm"
                          >
                            {day.label}
                          </ToggleGroupItem>
                        </TooltipTrigger>
                        <TooltipContent><p>{day.fullName}</p></TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  ))}
                </ToggleGroup>
              </div>

              {/* Intervalo entre mensagens */}
              <div className="space-y-4 pt-4 border-t">
                <div className="flex items-center justify-between">
                  <Label className="flex items-center gap-2">
                    Intervalo entre mensagens
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger>
                          <Info className="h-4 w-4 text-muted-foreground" />
                        </TooltipTrigger>
                        <TooltipContent>
                          <p>Tempo aleatório entre os envios.</p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </Label>
                  <Badge variant="outline" className="font-mono">
                    {intervalMin}s - {intervalMax}s
                  </Badge>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">Mínimo (segundos)</Label>
                    <Input 
                      type="number" 
                      value={intervalMin} 
                      onChange={(e) => setIntervalMin(Math.max(10, Number(e.target.value)))}
                      min={10}
                      className="font-mono"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">Máximo (segundos)</Label>
                    <Input 
                      type="number" 
                      value={intervalMax} 
                      onChange={(e) => setIntervalMax(Math.max(intervalMin + 5, Number(e.target.value)))}
                      min={intervalMin + 5}
                      className="font-mono"
                    />
                  </div>
                </div>
              </div>

              {/* Limite e Estimativa */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-4 border-t">
                <div className="space-y-2">
                  <Label>Limite Diário</Label>
                  <Select value={String(dailyLimit)} onValueChange={(v) => setDailyLimit(Number(v))}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="100">100 (Seguro)</SelectItem>
                      <SelectItem value="300">300 (Recomendado)</SelectItem>
                      <SelectItem value="500">500 (Moderado)</SelectItem>
                      <SelectItem value="1000">1000 (Alto Volume)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
                  <div className="flex items-start gap-2">
                    <Info className="h-4 w-4 text-slate-500 mt-0.5" />
                    <div className="text-sm">
                      <p className="font-medium text-slate-700">Previsão</p>
                      <p className="text-slate-600">
                        ~{messagesPerHour} envios/hora<br/>
                        Demora: <strong>~{daysToComplete} dia{daysToComplete > 1 ? 's' : ''}</strong>
                      </p>
                    </div>
                  </div>
                </div>
              </div>

            </TabsContent>
          </Tabs>

          <DialogFooter className="gap-2 sm:gap-0 mt-4">
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button 
              onClick={handleCreate} 
              disabled={isCreating || leadsWithWhatsApp.length === 0}
              className="bg-[#F59600] hover:bg-[#e08900] text-white font-semibold"
            >
              {isCreating ? (
                <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Criando...</>
              ) : (
                <><Check className="mr-2 h-4 w-4" /> Iniciar Disparos</>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
