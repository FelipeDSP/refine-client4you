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
  start?: number; // <-- ADICIONADO AQUI
}

interface SerpAPIResult {
  place_id: string;
  title: string;
  address: string;
  phone?: string;
  website?: string;
  rating?: number;
  reviews?: number;
  type?: string;
}

Deno.serve(async (req) => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const supabase = createClient(supabaseUrl, supabaseServiceKey);

    // Get authorization header
    const authHeader = req.headers.get("Authorization");
    if (!authHeader) {
      return new Response(
        JSON.stringify({ error: "Missing authorization header" }),
        { status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Verify JWT and get user
    const token = authHeader.replace("Bearer ", "");
    const { data: { user }, error: authError } = await supabase.auth.getUser(token);

    if (authError || !user) {
      return new Response(
        JSON.stringify({ error: "Invalid token" }),
        { status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    const body: SearchRequest = await req.json();
    const { query, location, companyId, searchId, start = 0 } = body; // <-- LENDO O START (Default: 0)

    // Validate required fields
    if (!query || !location || !companyId || !searchId) {
      return new Response(
        JSON.stringify({ error: "Missing required fields" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Authorization check
    const { data: userProfile, error: profileError } = await supabase
      .from('profiles')
      .select('company_id')
      .eq('id', user.id)
      .single();

    if (profileError || !userProfile || userProfile.company_id !== companyId) {
      console.warn('Authorization violation attempt detected');
      return new Response(
        JSON.stringify({ error: "Unauthorized" }),
        { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Input validation
    const maxQueryLength = 200;
    const maxLocationLength = 100;

    if (typeof query !== 'string' || typeof location !== 'string') {
      return new Response(
        JSON.stringify({ error: "Query and location must be strings" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    if (query.length > maxQueryLength || location.length > maxLocationLength) {
      return new Response(
        JSON.stringify({ error: `Query must be under ${maxQueryLength} characters and location under ${maxLocationLength} characters` }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Sanitize inputs
    const sanitizedQuery = query.trim().replace(/[^a-zA-Z0-9\s.,\-'áéíóúàèìòùâêîôûãõçñÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÃÕÇÑ]/gi, '');
    const sanitizedLocation = location.trim().replace(/[^a-zA-Z0-9\s.,\-'áéíóúàèìòùâêîôûãõçñÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÃÕÇÑ]/gi, '');

    if (!sanitizedQuery || !sanitizedLocation) {
      return new Response(
        JSON.stringify({ error: "Query and location cannot be empty after sanitization" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    const sqlPattern = /(union\s+select|insert\s+into|update\s+.+\s+set|delete\s+from|drop\s+table|exec\s*\(|script\s*>)/i;
    if (sqlPattern.test(query) || sqlPattern.test(location)) {
      console.warn("Potential SQL injection attempt detected:", { query: query.substring(0, 50), location: location.substring(0, 50) });
      return new Response(
        JSON.stringify({ error: "Invalid input detected" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Get company settings
    const { data: settings, error: settingsError } = await supabase
      .from("company_settings")
      .select("serpapi_key, waha_api_url, waha_api_key, waha_session")
      .eq("company_id", companyId)
      .maybeSingle();

    if (settingsError) {
      return new Response(
        JSON.stringify({ error: "Failed to fetch company settings" }),
        { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    const serpapiKey = settings?.serpapi_key;
    let leads: any[] = [];
    let hasMore = false; // <-- ESTADO DE PAGINAÇÃO

    if (serpapiKey) {
      console.log(`Using SerpAPI for search... (Start: ${start})`);
      
      const searchQuery = `${sanitizedQuery} em ${sanitizedLocation}`;
      // ADICIONADO O &start=${start} NA URL DA API 👇
      const serpApiUrl = `https://serpapi.com/search.json?engine=google_maps&q=${encodeURIComponent(searchQuery)}&api_key=${serpapiKey}&hl=pt-br&gl=br&start=${start}`;

      try {
        const serpResponse = await fetch(serpApiUrl);
        const serpData = await serpResponse.json();

        if (serpData.error) {
          console.error("SerpAPI error:", serpData.error);
          const errorMessage = String(serpData.error).toLowerCase();
          let clientError = "Search service temporarily unavailable";
          let statusCode = 503;
          
          if (errorMessage.includes('api key') || errorMessage.includes('invalid') || errorMessage.includes('unauthorized')) {
            clientError = "Search service configuration error. Please contact support.";
            statusCode = 500;
          } else if (errorMessage.includes('rate') || errorMessage.includes('limit') || errorMessage.includes('quota')) {
            clientError = "Search rate limit reached. Please try again later.";
            statusCode = 429;
          }
          
          return new Response(
            JSON.stringify({ error: clientError }),
            { status: statusCode, headers: { ...corsHeaders, "Content-Type": "application/json" } }
          );
        }

        // Verifica se a API indica que tem mais páginas
        hasMore = !!serpData.serpapi_pagination?.next;
        const localResults = serpData.local_results || [];

        // --- LÓGICA DE DEDUPLICAÇÃO DE OVERLAP ---
        // 1. Busca os nomes que já existem NESSA PESQUISA para evitar repetições
        const { data: existingLeads } = await supabase
          .from("leads")
          .select("name")
          .eq("search_id", searchId);

        const existingNames = new Set((existingLeads || []).map(l => (l.name || "").toLowerCase().trim()));

        // 2. Filtra os resultados mantendo apenas os INÉDITOS
        const uniqueLocalResults = localResults.filter((result: SerpAPIResult) => 
          !existingNames.has((result.title || "").toLowerCase().trim())
        );

        console.log(`API trouxe ${localResults.length} leads. Após deduplicação sobraram: ${uniqueLocalResults.length}`);

        // 3. Processa apenas os inéditos
        leads = uniqueLocalResults.map((result: SerpAPIResult) => {
          return {
            name: result.title,
            phone: result.phone || null,
            has_whatsapp: false, 
            email: null,
            has_email: false,
            address: result.address,
            category: result.type || query,
            rating: result.rating || null,
            reviews_count: result.reviews || 0,
            website: result.website || null,
            company_id: companyId,
            search_id: searchId,
          };
        });

        // WAHA Validation...
        if (settings?.waha_api_url && settings?.waha_api_key && settings?.waha_session) {
          const wahaSession = settings.waha_session;
          console.log("WAHA Configuration found - validating", leads.filter(l => l.phone).length, "leads");
          
          for (const lead of leads) {
            if (lead.phone) {
              try {
                const cleanPhone = lead.phone.replace(/\D/g, "");
                const phoneWithCountry = cleanPhone.startsWith("55") ? cleanPhone : `55${cleanPhone}`;
                const wahaUrl = `${settings.waha_api_url}/api/contacts/check-exists?phone=${phoneWithCountry}&session=${wahaSession}`;
                
                const wahaResponse = await fetch(wahaUrl, {
                  method: "GET",
                  headers: {
                    "Content-Type": "application/json",
                    "X-Api-Key": settings.waha_api_key,
                  },
                });

                if (wahaResponse.ok) {
                  const wahaData = await wahaResponse.json();
                  lead.has_whatsapp = wahaData.numberExists === true;
                }
              } catch (wahaError) {
                // Ignore error silently
              }
            }
          }
        }
      } catch (serpError) {
        return new Response(
          JSON.stringify({ error: "Failed to fetch from SerpAPI" }),
          { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }
    } else {
      // Usando MOCK DATA (Dados falsos)
      console.log(`No SerpAPI key configured, using mock data for start=${start}...`);
      const mockCount = 20; 
      const categories = [query, `${query} Premium`, `${query} Express`];
      const streets = ["Rua das Flores", "Av. Brasil", "Rua São Paulo", "Av. Paulista", "Rua Augusta"];
      
      // Simula que a página 3 (start 40) não tem mais resultados
      hasMore = start < 40;

      if (hasMore) {
        leads = Array.from({ length: mockCount }, (_, i) => {
          const hasWhatsApp = Math.random() > 0.3;
          return {
            name: `${query} ${location} (Pg ${Math.floor(start/20) + 1}) #${i + 1}`,
            phone: `(11) 9${Math.floor(1000 + Math.random() * 9000)}-${Math.floor(1000 + Math.random() * 9000)}`,
            has_whatsapp: hasWhatsApp,
            email: null,
            has_email: false,
            address: `${streets[Math.floor(Math.random() * streets.length)]}, ${Math.floor(100 + Math.random() * 2000)} - ${location}`,
            category: categories[Math.floor(Math.random() * categories.length)],
            rating: parseFloat((3 + Math.random() * 2).toFixed(1)),
            reviews_count: Math.floor(10 + Math.random() * 500),
            website: null,
            company_id: companyId,
            search_id: searchId,
          };
        });
      }
    }

    // Insert leads into database
    if (leads.length > 0) {
      const { error: insertError } = await supabase.from("leads").insert(leads);
      if (insertError) {
        console.error("Error inserting leads:", insertError);
        return new Response(
          JSON.stringify({ error: "Failed to save leads" }),
          { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }
    }

    // Retorna para o Frontend com os parâmetros hasMore e nextStart
    return new Response(
      JSON.stringify({ 
        success: true, 
        count: leads.length,
        usedRealApi: Boolean(serpapiKey),
        hasMore: hasMore,                     // <-- Informa o frontend se pode avançar
        nextStart: hasMore ? start + 20 : 0   // <-- Próxima página é +20
      }),
      { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  } catch (error) {
    console.error("Unexpected error:", error);
    return new Response(
      JSON.stringify({ error: "Internal server error" }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
