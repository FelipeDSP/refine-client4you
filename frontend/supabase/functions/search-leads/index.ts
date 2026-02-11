import { createClient } from "https://esm.sh/@supabase/supabase-js@2.49.1";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

interface SearchRequest {
  query: string;
  location: string;
  companyId: string;
  searchId: string;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: corsHeaders });

  try {
    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const supabase = createClient(supabaseUrl, supabaseServiceKey);

    const authHeader = req.headers.get("Authorization");
    if (!authHeader) throw new Error("Missing auth header");

    const body: SearchRequest = await req.json();
    const { query, location, companyId, searchId } = body;

    // Busca Configurações
    const { data: settings } = await supabase
      .from("company_settings")
      .select("serpapi_key")
      .eq("company_id", companyId)
      .maybeSingle();

    const serpapiKey = settings?.serpapi_key;
    let leads: any[] = [];

    if (serpapiKey) {
      console.log(`Searching SerpAPI: ${query} in ${location}`);
      const searchQuery = `${query} em ${location}`;
      const serpApiUrl = `https://serpapi.com/search.json?engine=google_maps&q=${encodeURIComponent(searchQuery)}&api_key=${serpapiKey}&hl=pt-br&gl=br&num=20`;

      const serpResponse = await fetch(serpApiUrl);
      const serpData = await serpResponse.json();

      if (serpData.error) throw new Error(serpData.error);

      leads = (serpData.local_results || []).map((result: any) => ({
        name: result.title,
        phone: result.phone || null,
        // IMPORTANTE: Deixamos false aqui para o Python validar depois
        has_whatsapp: false, 
        address: result.address,
        category: result.type || query,
        rating: result.rating || null,
        reviews_count: result.reviews || 0,
        website: result.website || null,
        company_id: companyId,
        search_id: searchId,
      }));
    } else {
      // Mock data se não tiver chave (para testes)
      console.log("Using Mock Data");
      leads = Array.from({ length: 5 }, (_, i) => ({
        name: `${query} Teste ${i+1}`,
        phone: `(11) 99999-000${i}`,
        has_whatsapp: false,
        address: `${location}, Rua ${i}`,
        company_id: companyId,
        search_id: searchId
      }));
    }

    // Salva no Banco
    if (leads.length > 0) {
      const { error } = await supabase.from("leads").insert(leads);
      if (error) throw error;
    }

    // Atualiza histórico
    await supabase.from("search_history")
      .update({ results_count: leads.length })
      .eq("id", searchId);

    return new Response(
      JSON.stringify({ success: true, count: leads.length }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );

  } catch (error) {
    console.error("Error:", error);
    return new Response(
      JSON.stringify({ error: error.message }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});