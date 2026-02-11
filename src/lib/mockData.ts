import { Lead, SearchHistory } from "@/types";

export const mockLeads: Lead[] = [
  {
    id: "1",
    name: "Pizzaria Bella Italia",
    phone: "(11) 99876-5432",
    hasWhatsApp: true,
    email: "contato@bellaitalia.com.br",
    address: "Rua Augusta, 1234",
    city: "São Paulo",
    state: "SP",
    rating: 4.5,
    reviews: 234,
    category: "Pizzaria",
    website: "www.bellaitalia.com.br",
    extractedAt: new Date().toISOString(),
  },
  {
    id: "2",
    name: "Restaurante Sabor Mineiro",
    phone: "(11) 98765-4321",
    hasWhatsApp: true,
    email: "contato@sabormineiro.com.br",
    address: "Av. Paulista, 567",
    city: "São Paulo",
    state: "SP",
    rating: 4.8,
    reviews: 456,
    category: "Restaurante",
    website: "www.sabormineiro.com.br",
    extractedAt: new Date().toISOString(),
  },
  {
    id: "3",
    name: "Hamburgueria The Burger",
    phone: "(11) 4567-8901",
    hasWhatsApp: false,
    email: null,
    address: "Rua Oscar Freire, 890",
    city: "São Paulo",
    state: "SP",
    rating: 4.2,
    reviews: 189,
    category: "Hamburgueria",
    website: null,
    extractedAt: new Date().toISOString(),
  },
  {
    id: "4",
    name: "Sushi Yamamoto",
    phone: "(11) 97654-3210",
    hasWhatsApp: true,
    email: "reservas@sushiyamamoto.com.br",
    address: "Rua Liberdade, 321",
    city: "São Paulo",
    state: "SP",
    rating: 4.9,
    reviews: 567,
    category: "Japonês",
    website: "www.sushiyamamoto.com.br",
    extractedAt: new Date().toISOString(),
  },
  {
    id: "5",
    name: "Padaria Pão Quente",
    phone: "(11) 96543-2109",
    hasWhatsApp: true,
    email: null,
    address: "Av. Brasil, 1500",
    city: "São Paulo",
    state: "SP",
    rating: 4.3,
    reviews: 312,
    category: "Padaria",
    website: null,
    extractedAt: new Date().toISOString(),
  },
];

export const mockSearchHistory: SearchHistory[] = [
  {
    id: "1",
    query: "Pizzarias",
    location: "São Paulo, SP",
    resultsCount: 45,
    searchedAt: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
  },
  {
    id: "2",
    query: "Restaurantes",
    location: "São Paulo, SP",
    resultsCount: 120,
    searchedAt: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(),
  },
];

// Type assertion helper for the generator function return type
type MockLead = {
  id: string;
  name: string;
  phone: string;
  hasWhatsApp: boolean;
  email: string | null;
  address: string;
  city: string;
  state: string;
  rating: number;
  reviews: number;
  category: string;
  website: string | null;
  extractedAt: string;
};

// Mapeamento de categorias para nomes realistas de estabelecimentos
const businessNamesByCategory: Record<string, string[]> = {
  // Postos de Gasolina
  "posto": ["Posto Shell", "Posto Ipiranga", "Posto BR", "Auto Posto", "Posto Petrobras", "Posto Ale", "Posto Formula", "Posto 24h", "Posto São Luiz", "Rede Cidade"],
  "gasolina": ["Posto Shell", "Posto Ipiranga", "Posto BR", "Auto Posto", "Posto Petrobras", "Posto Ale", "Posto Formula", "Posto 24h", "Posto São Luiz", "Rede Cidade"],
  "combustível": ["Posto Shell", "Posto Ipiranga", "Posto BR", "Auto Posto", "Posto Petrobras", "Posto Ale", "Posto Formula", "Posto 24h", "Posto São Luiz", "Rede Cidade"],
  
  // Restaurantes
  "restaurante": ["Restaurante Sabor da Terra", "Cantina Italiana", "Churrascaria Gaúcha", "Restaurante Família", "Bistrô Gourmet", "Cozinha da Vovó", "Tempero Caseiro", "Sabor & Arte", "Mesa Farta", "Delícias do Chef"],
  "pizzaria": ["Pizzaria Bella", "Pizza Express", "Napolitana Pizzas", "Pizzaria do Bairro", "La Pizza", "Forneria", "Pizza Prime", "Pizzaria Tradição", "Slice Pizza", "Don Corleone Pizzas"],
  "hamburgueria": ["Burger King", "The Burger", "Smash Burger", "Artesanal Burgers", "Burguer Mania", "Mega Burger", "House of Burgers", "Grill Burger", "Prime Burgers", "Street Burger"],
  "lanchonete": ["Lanchonete Central", "Snack Bar", "Lanchonete Express", "Cantinho do Lanche", "Fast Lanches", "Point do Lanche", "Lanchonete Popular", "Sabor Lanches", "Top Lanches", "Mega Lanches"],
  
  // Saúde
  "dentista": ["Clínica Odonto", "Sorria Odontologia", "Dental Center", "Odonto Saúde", "Clínica Dental", "Sorriso Perfeito", "Odonto Plus", "Dental Care", "Clínica Oral", "Prime Odonto"],
  "médico": ["Clínica Médica", "Centro Médico", "Saúde & Vida", "Clínica Popular", "Med Center", "Clínica Saúde", "Consultório Médico", "Vida Plena", "Clínica Bem Estar", "Medical Center"],
  "farmácia": ["Drogaria Popular", "Farmácia São João", "Droga Raia", "Pague Menos", "Farmácia Central", "Drogasil", "Farmácia Econômica", "Droga Fácil", "Farmácia 24h", "Farma Bem"],
  
  // Comércio
  "mercado": ["Supermercado Bom Preço", "Mercado Central", "Super Mix", "Atacadão", "Mercado Popular", "Supermercado Família", "Hiper Bom", "Mercado Extra", "Super Econômico", "Mercado União"],
  "supermercado": ["Supermercado Bom Preço", "Mercado Central", "Super Mix", "Atacadão", "Mercado Popular", "Supermercado Família", "Hiper Bom", "Mercado Extra", "Super Econômico", "Mercado União"],
  "loja": ["Loja Central", "Magazine", "Store Express", "Loja Popular", "Centro Comercial", "Mega Store", "Shop Center", "Loja do Povo", "Varejo & Cia", "Loja Econômica"],
  
  // Serviços
  "oficina": ["Auto Mecânica", "Oficina do João", "Car Service", "Mecânica Express", "Auto Center", "Oficina Popular", "Manutenção Automotiva", "Pit Stop", "Auto Reparos", "Mecânica Boa Vista"],
  "mecânica": ["Auto Mecânica", "Oficina do João", "Car Service", "Mecânica Express", "Auto Center", "Oficina Popular", "Manutenção Automotiva", "Pit Stop", "Auto Reparos", "Mecânica Boa Vista"],
  "salão": ["Salão de Beleza", "Studio Hair", "Beauty Center", "Espaço Beleza", "Cabelos & Cia", "Hair Design", "Salão Glamour", "Studio Beauty", "Beleza Pura", "Art Hair"],
  "barbearia": ["Barbearia Clássica", "Barber Shop", "Navalha de Ouro", "Barbearia do Mestre", "The Barber", "Corte & Estilo", "Barbearia Retrô", "Men's Hair", "Barbearia Masculina", "Old School Barber"],
  
  // Hospedagem
  "hotel": ["Hotel Central", "Pousada Bela Vista", "Hotel Conforto", "Palace Hotel", "Hotel Econômico", "Pousada do Sol", "Hotel Premium", "Inn Express", "Hotel Plaza", "Pousada Aconchego"],
  "pousada": ["Pousada Recanto", "Pousada Bela Vista", "Pousada do Sol", "Pousada Aconchego", "Pousada Familiar", "Recanto Verde", "Pousada Jardim", "Chalés da Serra", "Pousada Boa Vista", "Refúgio da Natureza"],
  
  // Default
  "default": ["Estabelecimento Local", "Comércio Central", "Empresa Popular", "Serviço Express", "Centro Comercial", "Negócio Local", "Ponto Comercial", "Empreendimento", "Empresa Familiar", "Serviços Gerais"],
};

function getBusinessNames(query: string): string[] {
  const queryLower = query.toLowerCase();
  
  for (const [key, names] of Object.entries(businessNamesByCategory)) {
    if (queryLower.includes(key)) {
      return names;
    }
  }
  
  return businessNamesByCategory["default"];
}

function formatCategory(query: string): string {
  const words = query.split(" ");
  return words.map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()).join(" ");
}

export function generateMockLeads(query: string, location: string, count: number = 20): Lead[] {
  const businessNames = getBusinessNames(query);
  const city = location.split(",")[0]?.trim() || "São Paulo";
  const state = location.split(",")[1]?.trim() || "SP";
  
  const streets = [
    "Av. Principal", "Rua Central", "Av. Brasil", "Rua Comercial", "Av. das Nações",
    "Rua 7 de Setembro", "Av. JK", "Rua 15 de Novembro", "Av. Rio Branco", "Rua da Paz"
  ];

  return Array.from({ length: count }, (_, i): Lead => {
    const baseName = businessNames[i % businessNames.length];
    const suffix = i >= businessNames.length ? ` ${city} ${Math.floor(i / businessNames.length) + 1}` : ` ${city}`;
    
    // Gera DDD baseado no estado
    const ddd = state === "RO" ? "69" : state === "SP" ? "11" : state === "RJ" ? "21" : "11";
    
    // Gera email baseado no nome do estabelecimento
    const emailBase = baseName.toLowerCase().replace(/\s/g, "").replace(/[^a-z0-9]/g, "");
    const hasEmail = Math.random() > 0.4;
    const hasWhatsApp = Math.random() > 0.3;
    
    return {
      id: `generated-${Date.now()}-${i}`,
      name: `${baseName}${suffix}`,
      phone: `(${ddd}) 9${Math.floor(1000 + Math.random() * 9000)}-${Math.floor(1000 + Math.random() * 9000)}`,
      hasWhatsApp,
      email: hasEmail ? `contato@${emailBase}.com.br` : null,
      address: `${streets[Math.floor(Math.random() * streets.length)]}, ${Math.floor(100 + Math.random() * 2000)}`,
      city,
      state,
      rating: Math.round((3.5 + Math.random() * 1.5) * 10) / 10,
      reviews: Math.floor(50 + Math.random() * 500),
      category: formatCategory(query),
      website: Math.random() > 0.4 ? `www.${emailBase}.com.br` : null,
      extractedAt: new Date().toISOString(),
    };
  });
}
