import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Check, Star, Search, Send, Bot, ArrowRight, Zap, Users, TrendingUp, Shield, ChevronDown, BarChart3, Clock, Globe } from "lucide-react";
import { Link, Navigate } from "react-router-dom";
import { plans } from "@/hooks/useSubscription";
import { useAuth } from "@/hooks/useAuth";
import { motion, useInView } from "framer-motion";
import { useRef } from "react";

// Checkout links
const CHECKOUT_LINKS: Record<string, string> = {
  basico: "https://pay.kiwify.com.br/FzhyShi",
  intermediario: "https://pay.kiwify.com.br/YlIDqCN",
  avancado: "https://pay.kiwify.com.br/TnUQl3f"
};

// Animation variants
const fadeUp = {
  hidden: { opacity: 0, y: 40 },
  visible: (i: number = 0) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.6, delay: i * 0.15, ease: "easeOut" as const }
  })
};

const fadeIn = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.8 } }
};

const scaleIn = {
  hidden: { opacity: 0, scale: 0.9 },
  visible: (i: number = 0) => ({
    opacity: 1,
    scale: 1,
    transition: { duration: 0.5, delay: i * 0.1, ease: "easeOut" as const }
  })
};

const stagger = {
  visible: { transition: { staggerChildren: 0.12 } }
};

function AnimatedSection({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-80px" });
  return (
    <motion.div
      ref={ref}
      initial="hidden"
      animate={isInView ? "visible" : "hidden"}
      variants={stagger}
      className={className}
    >
      {children}
    </motion.div>
  );
}

// Stats counter component
const stats = [
  { value: "10K+", label: "Leads Gerados", icon: Users },
  { value: "500+", label: "Empresas Ativas", icon: TrendingUp },
  { value: "95%", label: "Taxa de Entrega", icon: Zap },
  { value: "24/7", label: "Suporte Ativo", icon: Clock },
];

export default function LandingPage() {
  const { user, isLoading } = useAuth();
  
  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }
  
  if (user) {
    return <Navigate to="/dashboard" replace />;
  }
  
  return (
    <div className="min-h-screen bg-background overflow-x-hidden">
      {/* Header/Navbar */}
      <motion.header
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.5 }}
        className="sticky top-0 z-50 w-full border-b bg-background/80 backdrop-blur-xl"
      >
        <div className="container relative flex h-16 items-center justify-between">
          <div className="flex items-center gap-2">
            <img src="/client4you-icon.png" alt="Client4you" className="h-8 w-8 rounded" />
            <span className="text-xl font-bold">Client4you</span>
          </div>
          
          <nav className="hidden md:flex gap-8 absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
            <a href="#features" className="text-sm font-medium text-muted-foreground hover:text-primary transition-colors">Recursos</a>
            <a href="#how-it-works" className="text-sm font-medium text-muted-foreground hover:text-primary transition-colors">Como Funciona</a>
            <a href="#pricing" className="text-sm font-medium text-muted-foreground hover:text-primary transition-colors">Preços</a>
            <a href="#faq" className="text-sm font-medium text-muted-foreground hover:text-primary transition-colors">FAQ</a>
          </nav>
          
          <div className="flex items-center gap-3">
            <Link to="/login">
              <Button variant="ghost" size="sm">Entrar</Button>
            </Link>
            <a href="#pricing">
              <Button size="sm" className="gap-2 shadow-lg shadow-primary/30">
                Começar Agora
                <ArrowRight className="h-4 w-4" />
              </Button>
            </a>
          </div>
        </div>
      </motion.header>

      {/* Hero Section - Dark, Bold */}
      <section className="relative py-24 md:py-36 overflow-hidden bg-gradient-to-br from-foreground via-foreground/95 to-foreground/90">
        {/* Animated background elements */}
        <div className="absolute inset-0">
          <motion.div
            animate={{ scale: [1, 1.2, 1], opacity: [0.15, 0.25, 0.15] }}
            transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
            className="absolute top-20 left-[10%] w-96 h-96 bg-primary/30 rounded-full blur-[120px]"
          />
          <motion.div
            animate={{ scale: [1.2, 1, 1.2], opacity: [0.1, 0.2, 0.1] }}
            transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
            className="absolute bottom-10 right-[15%] w-80 h-80 bg-accent/20 rounded-full blur-[100px]"
          />
          <motion.div
            animate={{ scale: [1, 1.3, 1], opacity: [0.08, 0.15, 0.08] }}
            transition={{ duration: 12, repeat: Infinity, ease: "easeInOut" }}
            className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-secondary/10 rounded-full blur-[150px]"
          />
        </div>

        <div className="container relative z-10">
          <motion.div
            initial="hidden"
            animate="visible"
            variants={stagger}
            className="mx-auto max-w-5xl text-center space-y-8"
          >
            <motion.div variants={fadeUp} custom={0}>
              <Badge className="bg-primary/20 text-primary border-primary/30 backdrop-blur-sm text-sm px-4 py-1.5">
                🚀 Captação Inteligente de Clientes
              </Badge>
            </motion.div>
            
            <motion.h1 variants={fadeUp} custom={1} className="text-5xl md:text-7xl lg:text-8xl font-extrabold tracking-tight text-white leading-[0.9]">
              Do Lead à Conversão
              <br />
              <span className="text-primary">
                em Minutos
              </span>
            </motion.h1>
            
            <motion.p variants={fadeUp} custom={2} className="text-lg md:text-xl text-white/60 max-w-2xl mx-auto leading-relaxed">
              Plataforma completa para encontrar, contatar e converter clientes em escala.
              <span className="text-white/80 font-medium"> Extrator de leads + Disparador WhatsApp + IA.</span>
            </motion.p>
            
            <motion.div variants={fadeUp} custom={3} className="flex flex-col sm:flex-row gap-4 justify-center items-center pt-4">
              <a href="#pricing">
                <Button size="lg" className="text-lg h-14 px-10 gap-2 shadow-xl shadow-primary/40 font-bold">
                  Quero Começar Agora
                  <ArrowRight className="h-5 w-5" />
                </Button>
              </a>
              <a href="#how-it-works">
                <Button size="lg" variant="outline" className="text-lg h-14 px-10 border-white/20 text-white hover:bg-white/10 hover:text-white">
                  Como Funciona
                </Button>
              </a>
            </motion.div>
            
            <motion.div variants={fadeUp} custom={4} className="flex flex-wrap gap-6 justify-center text-sm text-white/50 pt-2">
              <span className="flex items-center gap-1.5"><Check className="h-4 w-4 text-secondary" /> Sem cartão de crédito</span>
              <span className="flex items-center gap-1.5"><Check className="h-4 w-4 text-secondary" /> Cancele quando quiser</span>
              <span className="flex items-center gap-1.5"><Check className="h-4 w-4 text-secondary" /> Setup em 5 minutos</span>
            </motion.div>
          </motion.div>

          {/* Scroll indicator */}
          <motion.div
            animate={{ y: [0, 8, 0] }}
            transition={{ duration: 2, repeat: Infinity }}
            className="flex justify-center mt-16"
          >
            <ChevronDown className="h-6 w-6 text-white/30" />
          </motion.div>
        </div>
      </section>

      {/* Social Proof / Stats Bar */}
      <section className="py-16 border-b bg-muted/30">
        <div className="container">
          <AnimatedSection className="grid grid-cols-2 md:grid-cols-4 gap-8">
            {stats.map((stat, i) => (
              <motion.div key={stat.label} variants={fadeUp} custom={i} className="text-center space-y-2">
                <stat.icon className="h-8 w-8 text-primary mx-auto mb-3" />
                <div className="text-3xl md:text-4xl font-extrabold text-foreground">{stat.value}</div>
                <div className="text-sm text-muted-foreground font-medium">{stat.label}</div>
              </motion.div>
            ))}
          </AnimatedSection>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-24">
        <div className="container">
          <AnimatedSection className="text-center space-y-4 mb-20">
            <motion.div variants={fadeUp}><Badge variant="secondary" className="text-sm">Recursos</Badge></motion.div>
            <motion.h2 variants={fadeUp} className="text-3xl md:text-5xl font-extrabold tracking-tight">
              Tudo que você precisa<br />
              <span className="text-primary">em uma única plataforma</span>
            </motion.h2>
            <motion.p variants={fadeUp} className="text-muted-foreground max-w-2xl mx-auto text-lg">
              Ferramentas poderosas integradas para automatizar todo o seu processo de captação de clientes.
            </motion.p>
          </AnimatedSection>
          
          <div className="grid md:grid-cols-3 gap-6 max-w-6xl mx-auto">
            {[
              {
                icon: Search,
                title: "Extrator de Leads",
                description: "Encontre milhares de leads qualificados direto do Google Maps em segundos.",
                features: ["Busca por segmento e localização", "Dados completos (nome, telefone, email)", "Exportação para Excel/CSV"],
                gradient: "from-primary/10 to-primary/5"
              },
              {
                icon: Send,
                title: "Disparador WhatsApp",
                description: "Envie mensagens personalizadas em massa via WhatsApp de forma automatizada.",
                features: ["Conexão simplificada via QR Code", "Mensagens com variáveis dinâmicas", "Agendamento e controle de horários"],
                popular: true,
                gradient: "from-secondary/10 to-secondary/5"
              },
              {
                icon: Bot,
                title: "Agente IA Personalizado",
                description: "Automação inteligente que qualifica leads e responde automaticamente.",
                features: ["Respostas automáticas inteligentes", "Qualificação de leads com IA", "Follow-up automatizado"],
                gradient: "from-accent/10 to-accent/5"
              }
            ].map((feature, i) => (
              <AnimatedSection key={feature.title}>
                <motion.div variants={scaleIn} custom={i}>
                  <Card className={`h-full border-2 transition-all duration-300 hover:shadow-xl hover:-translate-y-1 ${feature.popular ? "border-primary shadow-lg shadow-primary/10" : "hover:border-primary/30"}`}>
                    <CardHeader>
                      {feature.popular && <Badge className="w-fit mb-2">Mais Popular</Badge>}
                      <div className={`h-14 w-14 rounded-2xl bg-gradient-to-br ${feature.gradient} flex items-center justify-center mb-4`}>
                        <feature.icon className="h-7 w-7 text-primary" />
                      </div>
                      <CardTitle className="text-xl">{feature.title}</CardTitle>
                      <CardDescription className="text-base">{feature.description}</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <ul className="space-y-3">
                        {feature.features.map((f) => (
                          <li key={f} className="flex items-center gap-2.5 text-sm">
                            <div className="h-5 w-5 rounded-full bg-secondary/10 flex items-center justify-center flex-shrink-0">
                              <Check className="h-3 w-3 text-secondary" />
                            </div>
                            {f}
                          </li>
                        ))}
                      </ul>
                    </CardContent>
                  </Card>
                </motion.div>
              </AnimatedSection>
            ))}
          </div>
        </div>
      </section>

      {/* How it Works Section */}
      <section id="how-it-works" className="py-24 bg-gradient-to-b from-muted/50 to-background">
        <div className="container">
          <AnimatedSection className="text-center space-y-4 mb-20">
            <motion.div variants={fadeUp}><Badge variant="secondary" className="text-sm">Como Funciona</Badge></motion.div>
            <motion.h2 variants={fadeUp} className="text-3xl md:text-5xl font-extrabold tracking-tight">
              3 passos simples para<br />
              <span className="text-primary">escalar suas vendas</span>
            </motion.h2>
          </AnimatedSection>

          <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            {[
              { step: "01", title: "Busque Leads", desc: "Digite o segmento e a cidade. Nossa plataforma extrai dados de milhares de empresas em segundos.", icon: Search },
              { step: "02", title: "Crie Campanhas", desc: "Monte mensagens personalizadas com variáveis dinâmicas. Agende envios nos melhores horários.", icon: Send },
              { step: "03", title: "Converta Clientes", desc: "Acompanhe métricas em tempo real. Use IA para qualificar e responder leads automaticamente.", icon: BarChart3 }
            ].map((item, i) => (
              <AnimatedSection key={item.step}>
                <motion.div variants={fadeUp} custom={i} className="relative text-center space-y-4 p-6">
                  <div className="text-7xl font-black text-primary/10">{item.step}</div>
                  <div className="h-16 w-16 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto -mt-10 relative">
                    <item.icon className="h-8 w-8 text-primary" />
                  </div>
                  <h3 className="text-xl font-bold">{item.title}</h3>
                  <p className="text-muted-foreground leading-relaxed">{item.desc}</p>
                </motion.div>
              </AnimatedSection>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" className="py-24">
        <div className="container">
          <AnimatedSection className="text-center space-y-4 mb-16">
            <motion.div variants={fadeUp}><Badge variant="secondary" className="text-sm">Preços</Badge></motion.div>
            <motion.h2 variants={fadeUp} className="text-3xl md:text-5xl font-extrabold tracking-tight">
              Planos para todo<br />
              <span className="text-primary">tamanho de negócio</span>
            </motion.h2>
            <motion.p variants={fadeUp} className="text-muted-foreground text-lg">
              Escolha o plano ideal. Upgrade ou downgrade quando quiser.
            </motion.p>
          </AnimatedSection>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-6xl mx-auto">
            {plans.filter(p => !p.isDemo).map((plan, i) => {
              const isPopular = plan.id === "intermediario";
              const checkoutLink = CHECKOUT_LINKS[plan.id] || "#pricing";
              
              return (
                <AnimatedSection key={plan.id}>
                  <motion.div variants={scaleIn} custom={i}>
                    <Card className={`h-full transition-all duration-300 hover:shadow-xl hover:-translate-y-1 ${isPopular ? "border-primary border-2 shadow-xl shadow-primary/10 relative" : ""}`}>
                      {isPopular && (
                        <div className="absolute -top-3.5 left-1/2 -translate-x-1/2">
                          <Badge className="bg-primary shadow-lg px-4 py-1">
                            <Star className="h-3 w-3 mr-1 fill-current" />
                            Mais Popular
                          </Badge>
                        </div>
                      )}
                      
                      <CardHeader className="text-center pb-2">
                        <CardTitle className="text-xl">{plan.name}</CardTitle>
                        <CardDescription>{plan.description}</CardDescription>
                        <div className="pt-4 pb-2">
                          <span className="text-5xl font-extrabold">
                            {plan.price === 0 ? "Grátis" : `R$ ${plan.price.toFixed(2).replace('.', ',')}`}
                          </span>
                          {plan.price > 0 && <span className="text-muted-foreground text-lg">/mês</span>}
                        </div>
                      </CardHeader>
                      
                      <CardContent className="space-y-4">
                        <ul className="space-y-2.5 text-sm">
                          {plan.features.map((feature, idx) => (
                            <li key={idx} className="flex items-start gap-2.5">
                              {feature.included ? (
                                <div className="h-5 w-5 rounded-full bg-secondary/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                                  <Check className="h-3 w-3 text-secondary" />
                                </div>
                              ) : (
                                <span className="h-5 w-5 mt-0.5 flex-shrink-0 text-center text-muted-foreground">−</span>
                              )}
                              <div>
                                <span className={!feature.included ? "text-muted-foreground" : ""}>{feature.name}</span>
                                {feature.limit && feature.included && (
                                  <span className="text-xs text-muted-foreground block">{feature.limit}</span>
                                )}
                              </div>
                            </li>
                          ))}
                        </ul>
                        
                        <a href={checkoutLink} target="_blank" rel="noopener noreferrer" className="block">
                          <Button 
                            className={`w-full h-12 text-base font-semibold ${isPopular ? "shadow-lg shadow-primary/30" : ""}`}
                            variant={isPopular ? "default" : "outline"}
                          >
                            Assinar Agora
                          </Button>
                        </a>
                      </CardContent>
                    </Card>
                  </motion.div>
                </AnimatedSection>
              );
            })}
          </div>

          <AnimatedSection>
            <motion.p variants={fadeUp} className="text-center text-sm text-muted-foreground mt-10">
              Todos os planos incluem suporte, atualizações e podem ser cancelados a qualquer momento.
            </motion.p>
          </AnimatedSection>
        </div>
      </section>

      {/* FAQ Section */}
      <section id="faq" className="py-24 bg-muted/30">
        <div className="container">
          <AnimatedSection className="text-center space-y-4 mb-16">
            <motion.div variants={fadeUp}><Badge variant="secondary" className="text-sm">FAQ</Badge></motion.div>
            <motion.h2 variants={fadeUp} className="text-3xl md:text-5xl font-extrabold tracking-tight">
              Perguntas Frequentes
            </motion.h2>
          </AnimatedSection>

          <div className="max-w-3xl mx-auto space-y-4">
            {[
              { q: "Como funciona o período de teste?", a: "Garantia de 7 dias: se você não gostar, devolvemos 100% do seu dinheiro pela própria plataforma de pagamento." },
              { q: "Posso cancelar a qualquer momento?", a: "Sim! Todos os planos são sem fidelidade. Você pode cancelar quando quiser e continua tendo acesso até o fim do período pago." },
              { q: "Como funciona a conexão com WhatsApp?", a: "Nos planos Intermediário e Avançado, você conecta seu WhatsApp escaneando um QR Code. É rápido, seguro e não precisa de servidor próprio." },
              { q: "O Agente de IA está disponível?", a: "O Agente de IA personalizado está em desenvolvimento e será lançado em breve exclusivamente no plano Avançado." },
              { q: "Preciso de conhecimentos técnicos?", a: "Não! A plataforma foi desenvolvida para ser simples e intuitiva. Em 5 minutos você já consegue fazer sua primeira busca e enviar suas primeiras mensagens." }
            ].map((item, i) => (
              <AnimatedSection key={i}>
                <motion.div variants={fadeUp} custom={i}>
                  <Card className="transition-all duration-200 hover:shadow-md">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-lg font-semibold">{item.q}</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-muted-foreground leading-relaxed">{item.a}</p>
                    </CardContent>
                  </Card>
                </motion.div>
              </AnimatedSection>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Final */}
      <section className="py-24">
        <div className="container">
          <AnimatedSection>
            <motion.div variants={scaleIn} className="relative rounded-3xl overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-br from-foreground via-foreground/95 to-foreground/90" />
              <div className="absolute inset-0">
                <motion.div
                  animate={{ scale: [1, 1.3, 1], opacity: [0.2, 0.35, 0.2] }}
                  transition={{ duration: 6, repeat: Infinity }}
                  className="absolute top-10 right-20 w-60 h-60 bg-primary/40 rounded-full blur-[80px]"
                />
                <motion.div
                  animate={{ scale: [1.2, 1, 1.2], opacity: [0.1, 0.25, 0.1] }}
                  transition={{ duration: 8, repeat: Infinity }}
                  className="absolute bottom-10 left-20 w-40 h-40 bg-accent/30 rounded-full blur-[60px]"
                />
              </div>
              
              <div className="relative z-10 p-12 md:p-20 text-center space-y-8">
                <h2 className="text-3xl md:text-5xl font-extrabold text-white tracking-tight">
                  Pronto para captar<br />
                  <span className="text-primary">mais clientes?</span>
                </h2>
                <p className="text-lg text-white/60 max-w-xl mx-auto">
                  Junte-se a centenas de profissionais que já estão escalando suas vendas com Client4you
                </p>
                <a href="#pricing">
                  <Button size="lg" className="text-lg h-14 px-10 gap-2 shadow-xl shadow-primary/40 font-bold">
                    Ver Planos e Preços
                    <ArrowRight className="h-5 w-5" />
                  </Button>
                </a>
              </div>
            </motion.div>
          </AnimatedSection>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t py-16 bg-background">
        <div className="container">
          <div className="grid md:grid-cols-4 gap-10">
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <img src="/client4you-icon.png" alt="Client4you" className="h-8 w-8 rounded" />
                <span className="font-bold text-lg">Client4you</span>
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Captação inteligente de clientes para profissionais e empresas.
              </p>
            </div>

            <div>
              <h3 className="font-semibold mb-4">Produto</h3>
              <ul className="space-y-2.5 text-sm text-muted-foreground">
                <li><a href="#features" className="hover:text-primary transition-colors">Recursos</a></li>
                <li><a href="#pricing" className="hover:text-primary transition-colors">Preços</a></li>
                <li><Link to="/login" className="hover:text-primary transition-colors">Área do Cliente</Link></li>
              </ul>
            </div>

            <div>
              <h3 className="font-semibold mb-4">Suporte</h3>
              <ul className="space-y-2.5 text-sm text-muted-foreground">
                <li><a href="#faq" className="hover:text-primary transition-colors">FAQ</a></li>
                <li><a href="mailto:suporte@client4you.com.br" className="hover:text-primary transition-colors">Contato</a></li>
              </ul>
            </div>

            <div>
              <h3 className="font-semibold mb-4">Legal</h3>
              <ul className="space-y-2.5 text-sm text-muted-foreground">
                <li><a href="#" className="hover:text-primary transition-colors">Termos de Uso</a></li>
                <li><a href="#" className="hover:text-primary transition-colors">Privacidade</a></li>
              </ul>
            </div>
          </div>

          <div className="border-t mt-10 pt-10 text-center text-sm text-muted-foreground">
            <p>© 2025 Client4you. Todos os direitos reservados.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
