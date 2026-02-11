import { Users, Search, MessageCircle, TrendingUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Lead, SearchHistory } from "@/types";

interface StatsCardsProps {
  leads: Lead[];
  searchHistory: SearchHistory[];
}

export function StatsCards({ leads, searchHistory }: StatsCardsProps) {
  const leadsWithWhatsApp = leads.filter((l) => l.hasWhatsApp).length;
  const avgRating = leads.length > 0 
    ? (leads.reduce((acc, l) => acc + l.rating, 0) / leads.length).toFixed(1)
    : "0.0";

  const stats = [
    {
      title: "Total de Leads",
      value: leads.length,
      icon: Users,
      description: "Leads extraídos",
      color: "text-blue-600",
      bgColor: "bg-blue-100",
    },
    {
      title: "Buscas Realizadas",
      value: searchHistory.length,
      icon: Search,
      description: "Últimas 50 buscas",
      color: "text-purple-600",
      bgColor: "bg-purple-100",
    },
    {
      title: "Com WhatsApp",
      value: leadsWithWhatsApp,
      icon: MessageCircle,
      description: `${leads.length > 0 ? Math.round((leadsWithWhatsApp / leads.length) * 100) : 0}% dos leads`,
      color: "text-emerald-600",
      bgColor: "bg-emerald-100",
    },
    {
      title: "Avaliação Média",
      value: avgRating,
      icon: TrendingUp,
      description: "Nota média dos leads",
      color: "text-amber-600",
      bgColor: "bg-amber-100",
    },
  ];

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {stats.map((stat) => (
        <Card key={stat.title}>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{stat.title}</CardTitle>
            <div className={`rounded-lg p-2 ${stat.bgColor}`}>
              <stat.icon className={`h-4 w-4 ${stat.color}`} />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stat.value}</div>
            <p className="text-xs text-muted-foreground">{stat.description}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
