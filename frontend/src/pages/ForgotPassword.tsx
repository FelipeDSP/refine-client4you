import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Loader2, Mail, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const { toast } = useToast();

  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      const { error } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: `${window.location.origin}/update-password`,
      });
      if (error) throw error;

      setIsSubmitted(true);
      toast({ title: "E-mail enviado!", description: "Verifique sua caixa de entrada para redefinir a senha." });
    } catch (error: any) {
      toast({ title: "Erro ao enviar", description: error.message || "Tente novamente mais tarde.", variant: "destructive" });
    } finally {
      setIsLoading(false);
    }
  };

  const bgClasses = "relative flex min-h-screen items-center justify-center p-4 overflow-hidden bg-gradient-to-br from-foreground via-foreground/95 to-foreground/90";

  const bgBlobs = (
    <div className="absolute inset-0 pointer-events-none">
      <div className="absolute top-20 left-[10%] w-96 h-96 bg-primary/20 rounded-full blur-[120px] animate-pulse" />
      <div className="absolute bottom-10 right-[15%] w-80 h-80 bg-accent/15 rounded-full blur-[100px] animate-pulse" style={{ animationDelay: "1s" }} />
    </div>
  );

  if (isSubmitted) {
    return (
      <div className={bgClasses}>
        {bgBlobs}
        <div className="relative z-10 w-full max-w-md">
          <Link to="/login" className="inline-flex items-center text-sm text-white/50 hover:text-white/80 transition-colors mb-6 gap-1.5">
            <ArrowLeft className="h-4 w-4" />
            Voltar ao login
          </Link>
          <Card className="border-white/10 bg-white/5 backdrop-blur-xl shadow-2xl text-center">
            <CardHeader>
              <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-secondary/20">
                <CheckCircle2 className="h-8 w-8 text-secondary" />
              </div>
              <CardTitle className="text-white">Verifique seu E-mail</CardTitle>
              <CardDescription className="text-white/50">
                Enviamos um link de recuperação para <strong className="text-white/70">{email}</strong>
              </CardDescription>
            </CardHeader>
            <CardFooter className="justify-center">
              <Link to="/login">
                <Button variant="ghost" className="text-white/60 hover:text-white hover:bg-white/10">
                  <ArrowLeft className="mr-2 h-4 w-4" />
                  Voltar para o Login
                </Button>
              </Link>
            </CardFooter>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className={bgClasses}>
      {bgBlobs}
      <div className="relative z-10 w-full max-w-md">
        <Link to="/login" className="inline-flex items-center text-sm text-white/50 hover:text-white/80 transition-colors mb-6 gap-1.5">
          <ArrowLeft className="h-4 w-4" />
          Voltar ao login
        </Link>
        <Card className="border-white/10 bg-white/5 backdrop-blur-xl shadow-2xl">
          <CardHeader>
            <CardTitle className="text-white">Recuperar Senha</CardTitle>
            <CardDescription className="text-white/50">
              Digite seu e-mail para receber o link de redefinição
            </CardDescription>
          </CardHeader>
          <form onSubmit={handleReset}>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email" className="text-white/80">E-mail</Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/30" />
                  <Input
                    id="email"
                    type="email"
                    placeholder="seu@email.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="border-white/10 bg-white/5 pl-10 text-white placeholder:text-white/30 focus:border-primary"
                    required
                  />
                </div>
              </div>
            </CardContent>
            <CardFooter className="flex-col gap-4">
              <Button type="submit" className="w-full shadow-lg shadow-primary/30" disabled={isLoading}>
                {isLoading ? (
                  <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Enviando...</>
                ) : (
                  "Enviar Link"
                )}
              </Button>
            </CardFooter>
          </form>
        </Card>
      </div>
    </div>
  );
}
