import { createClient } from "https://esm.sh/@supabase/supabase-js@2.49.1";
import { createHash } from "https://deno.land/std@0.177.0/node/crypto.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

interface SearchRequest {
  action: 'create' | 'fetch_more' | 'complete';
  query?: string;
  location?: string;
  search_type?: 'serp' | 'cnae';
  session_id?: string;
  company_id?: string;
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

// Gerar fingerprint MD5
function generateFingerprint(name: string, address: string, phone: string): string {
  const data = `${(name || '').toLowerCase().trim()}|${(address || '').toLowerCase().trim()}|${(phone || '').replace(/\D/g, '')}`;
  return createHash('md5').update(data).digest('hex');
}

// Normalizar telefone
function normalizePhone(phone: string): string {
  const digits = phone.replace(/\D/g, '');
  if (digits.startsWith('55')) return digits;
  if (digits.startsWith('0')) return '55' + digits.substring(1);
  return '55' + digits;
}

Deno.serve(async (req) => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseAnonKey = Deno.env.get("SUPABASE_ANON_KEY")!;
    const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

    // Verificar autenticação
    const authHeader = req.headers.get("Authorization");
    if (!authHeader) {
      return new Response(
        JSON.stringify({ error: "Missing authorization header" }),
        { status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Usar anon key para validar o token do usuário
    const supabaseClient = createClient(supabaseUrl, supabaseAnonKey, {
      global: {
        headers: { Authorization: authHeader }
      }
    });

    const { data: { user }, error: authError } = await supabaseClient.auth.getUser();

    if (authError || !user) {
      console.error("Auth error:", authError);
      return new Response(
        JSON.stringify({ error: "Invalid token", details: authError?.message }),
        { status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Usar service role key para operações no banco
    const supabase = createClient(supabaseUrl, supabaseServiceKey);

    // Parse request body
    const body: SearchRequest = await req.json();
    const { action } = body;

    console.log(`[search-leads-v2] Action: ${action}, User: ${user.id}`);

    // ===== ACTION: CREATE NEW SEARCH SESSION =====
    if (action === 'create') {
      const { query, location, search_type = 'serp', company_id } = body;

      if (!query || !company_id) {
        return new Response(
          JSON.stringify({ error: "Missing query or company_id" }),
          { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      // Verificar autorização (usuário pertence à empresa)
      const { data: userProfile } = await supabase
        .from('profiles')
        .select('company_id')
        .eq('id', user.id)
        .single();

      if (!userProfile || userProfile.company_id !== company_id) {
        return new Response(
          JSON.stringify({ error: "Unauthorized" }),
          { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      // Criar sessão de busca
      const { data: session, error: sessionError } = await supabase
        .from('search_sessions')
        .insert({
          company_id,
          user_id: user.id,
          search_type,
          query: query.trim(),
          location: location?.trim(),
          current_page: 0,
          status: 'active'
        })
        .select()
        .single();

      if (sessionError) {
        console.error("Error creating session:", sessionError);
        return new Response(
          JSON.stringify({ error: "Failed to create search session" }),
          { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      // Buscar primeira página
      const results = await fetchSearchResults(supabase, session, 0);
      
      return new Response(
        JSON.stringify(results),
        { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // ===== ACTION: FETCH MORE RESULTS =====
    else if (action === 'fetch_more') {
      const { session_id } = body;

      if (!session_id) {
        return new Response(
          JSON.stringify({ error: "Missing session_id" }),
          { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      // Buscar sessão
      const { data: session, error: sessionError } = await supabase
        .from('search_sessions')
        .select('*')
        .eq('id', session_id)
        .single();

      if (sessionError || !session) {
        return new Response(
          JSON.stringify({ error: "Search session not found" }),
          { status: 404, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      // Verificar autorização
      const { data: userProfile } = await supabase
        .from('profiles')
        .select('company_id')
        .eq('id', user.id)
        .single();

      if (!userProfile || userProfile.company_id !== session.company_id) {
        return new Response(
          JSON.stringify({ error: "Unauthorized" }),
          { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      // Buscar próxima página
      const nextPage = session.current_page + 1;
      const results = await fetchSearchResults(supabase, session, nextPage);
      
      return new Response(
        JSON.stringify(results),
        { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // ===== ACTION: COMPLETE SESSION =====
    else if (action === 'complete') {
      const { session_id } = body;

      if (!session_id) {
        return new Response(
          JSON.stringify({ error: "Missing session_id" }),
          { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      await supabase
        .from('search_sessions')
        .update({
          status: 'completed',
          completed_at: new Date().toISOString()
        })
        .eq('id', session_id);

      return new Response(
        JSON.stringify({ success: true }),
        { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Ação inválida
    return new Response(
      JSON.stringify({ error: "Invalid action" }),
      { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );

  } catch (error) {
    console.error("Unexpected error:", error);
    return new Response(
      JSON.stringify({ error: "Internal server error" }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});

// ===== FUNÇÃO PRINCIPAL: BUSCAR RESULTADOS =====
async function fetchSearchResults(supabase: any, session: any, page: number) {
  const resultsPerPage = 20;
  const start = page * resultsPerPage;

  console.log(`[fetchSearchResults] Session: ${session.id}, Page: ${page}, Start: ${start}`);

  // Buscar configurações da empresa
  const { data: settings } = await supabase
    .from("company_settings")
    .select("serpapi_key, waha_api_url, waha_api_key, waha_session")
    .eq("company_id", session.company_id)
    .maybeSingle();

  const serpapiKey = settings?.serpapi_key;
  
  if (!serpapiKey) {
    // Sem API key - usar dados mock
    const mockResults = await generateMockResults(session, resultsPerPage);
    const processed = await processResults(supabase, mockResults, session);
    return processed;
  }

  // Buscar via SERP API
  try {
    const searchQuery = session.location 
      ? `${session.query} em ${session.location}`
      : session.query;

    const serpApiUrl = `https://serpapi.com/search.json?engine=google_maps&q=${encodeURIComponent(searchQuery)}&api_key=${serpapiKey}&hl=pt-br&gl=br&start=${start}`;
    
    console.log(`[SERP API] Fetching page ${page}...`);
    
    const serpResponse = await fetch(serpApiUrl);
    const serpData = await serpResponse.json();

    if (serpData.error) {
      console.error("SERP API error:", serpData.error);
      throw new Error(serpData.error);
    }

    const localResults = serpData.local_results || [];
    
    if (localResults.length === 0) {
      console.log(`[SERP API] No more results at page ${page}`);
      
      // Marcar sessão como completa
      await supabase
        .from('search_sessions')
        .update({ status: 'completed', completed_at: new Date().toISOString() })
        .eq('id', session.id);

      return {
        session_id: session.id,
        results: [],
        new_count: 0,
        duplicate_count: 0,
        current_page: page,
        has_more: false,
        status: 'completed'
      };
    }

    // Processar resultados
    const processed = await processResults(supabase, localResults, session, serpData.serpapi_pagination?.next);
    
    return processed;

  } catch (error) {
    console.error("SERP API request error:", error);
    
    // Marcar sessão com erro
    await supabase
      .from('search_sessions')
      .update({
        status: 'error',
        error_message: error.message
      })
      .eq('id', session.id);

    throw error;
  }
}

// ===== PROCESSAR RESULTADOS COM DEDUPLICAÇÃO =====
async function processResults(
  supabase: any, 
  results: any[], 
  session: any,
  hasMorePages = false
) {
  let newCount = 0;
  let duplicateCount = 0;
  const processedLeads: any[] = [];

  console.log(`[processResults] Processing ${results.length} results...`);

  for (const result of results) {
    const leadData = {
      name: result.title,
      phone: result.phone || null,
      address: result.address,
      category: result.type || session.query,
      rating: result.rating || null,
      reviews_count: result.reviews || 0,
      website: result.website || null,
    };

    // Gerar fingerprint
    const fingerprint = generateFingerprint(
      leadData.name, 
      leadData.address, 
      leadData.phone || ''
    );

    // Verificar se já existe
    const { data: existingLead } = await supabase
      .from('leads')
      .select('id, times_found, sources')
      .eq('company_id', session.company_id)
      .eq('fingerprint', fingerprint)
      .maybeSingle();

    if (existingLead) {
      // DUPLICADO - Atualizar
      console.log(`[DUPLICATE] ${leadData.name}`);
      
      const updatedSources = [
        ...(existingLead.sources || []),
        { session_id: session.id, found_at: new Date().toISOString() }
      ];

      await supabase
        .from('leads')
        .update({
          last_seen_at: new Date().toISOString(),
          times_found: existingLead.times_found + 1,
          sources: updatedSources
        })
        .eq('id', existingLead.id);

      duplicateCount++;
      processedLeads.push({
        ...leadData,
        id: existingLead.id,
        is_duplicate: true,
        times_found: existingLead.times_found + 1
      });

    } else {
      // NOVO - Inserir
      console.log(`[NEW] ${leadData.name}`);

      const { data: newLead, error: insertError } = await supabase
        .from('leads')
        .insert({
          ...leadData,
          company_id: session.company_id,
          search_id: session.id,
          fingerprint,
          times_found: 1,
          sources: [{ session_id: session.id, found_at: new Date().toISOString() }],
          has_whatsapp: false,
          has_email: false
        })
        .select()
        .single();

      if (insertError) {
        console.error("Error inserting lead:", insertError);
        continue;
      }

      newCount++;
      processedLeads.push({
        ...newLead,
        is_duplicate: false
      });
    }
  }

  // Atualizar sessão
  const { data: currentSession } = await supabase
    .from('search_sessions')
    .select('new_leads_count, duplicate_leads_count, current_page')
    .eq('id', session.id)
    .single();

  const newPage = Math.max(currentSession?.current_page || 0, session.current_page || 0) + 1;

  await supabase
    .from('search_sessions')
    .update({
      current_page: newPage,
      new_leads_count: (currentSession?.new_leads_count || 0) + newCount,
      duplicate_leads_count: (currentSession?.duplicate_leads_count || 0) + duplicateCount,
      total_results_found: (currentSession?.new_leads_count || 0) + (currentSession?.duplicate_leads_count || 0) + newCount + duplicateCount,
      last_fetch_at: new Date().toISOString()
    })
    .eq('id', session.id);

  console.log(`[processResults] New: ${newCount}, Duplicates: ${duplicateCount}`);

  return {
    session_id: session.id,
    results: processedLeads,
    new_count: newCount,
    duplicate_count: duplicateCount,
    current_page: newPage,
    has_more: hasMorePages && processedLeads.length === 20,
    total_new: (currentSession?.new_leads_count || 0) + newCount,
    total_duplicates: (currentSession?.duplicate_leads_count || 0) + duplicateCount
  };
}

// ===== GERAR DADOS MOCK =====
async function generateMockResults(session: any, count: number) {
  console.log(`[MOCK] Generating ${count} mock results...`);
  
  const categories = [session.query, `${session.query} Premium`, `${session.query} Express`];
  const streets = ["Rua das Flores", "Av. Brasil", "Rua São Paulo", "Av. Paulista", "Rua Augusta"];
  const location = session.location || "São Paulo";

  return Array.from({ length: count }, (_, i) => ({
    title: `${session.query} ${location} #${Math.floor(Math.random() * 1000)}`,
    phone: `(11) 9${Math.floor(1000 + Math.random() * 9000)}-${Math.floor(1000 + Math.random() * 9000)}`,
    address: `${streets[Math.floor(Math.random() * streets.length)]}, ${Math.floor(100 + Math.random() * 2000)} - ${location}`,
    type: categories[Math.floor(Math.random() * categories.length)],
    rating: parseFloat((3 + Math.random() * 2).toFixed(1)),
    reviews: Math.floor(10 + Math.random() * 500),
    website: Math.random() > 0.5 ? `https://www.empresa${i + 1}.com.br` : null,
  }));
}
