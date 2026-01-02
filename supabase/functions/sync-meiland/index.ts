// Supabase Edge Function: sync-meiland
// Syncs data from Liga Meiland to Supabase
// Deploy with: supabase functions deploy sync-meiland

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const MEILAND_BASE = "https://app.meiland.es";
const TEAM_ID = "5253";
const DIVISION_ID = "699";

// Credentials stored in Supabase secrets
const MEILAND_EMAIL = Deno.env.get("MEILAND_EMAIL") || "";
const MEILAND_PASSWORD = Deno.env.get("MEILAND_PASSWORD") || "";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

interface MeilandSession {
  cookies: string;
  csrfToken?: string;
}

// Login to Meiland and get session cookies
async function loginToMeiland(): Promise<MeilandSession | null> {
  try {
    // First, get the login page to extract CSRF token
    const loginPageRes = await fetch(`${MEILAND_BASE}/app/user/login`, {
      method: "GET",
      headers: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
      },
    });

    const cookies = loginPageRes.headers.get("set-cookie") || "";
    const loginPageHtml = await loginPageRes.text();

    // Extract CSRF token - Meiland uses "_csrf-backend"
    const csrfMatch = loginPageHtml.match(/name="_csrf-backend"\s+value="([^"]+)"/);
    const csrfToken = csrfMatch ? csrfMatch[1] : "";

    console.log("CSRF token found:", csrfToken ? "YES" : "NO");

    // Perform login
    const formData = new URLSearchParams();
    formData.append("LoginForm[email]", MEILAND_EMAIL);
    formData.append("LoginForm[password]", MEILAND_PASSWORD);
    formData.append("LoginForm[rememberMe]", "1");
    if (csrfToken) {
      formData.append("_csrf-backend", csrfToken);
    }

    const loginRes = await fetch(`${MEILAND_BASE}/app/user/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Cookie": cookies,
      },
      body: formData.toString(),
      redirect: "manual",
    });

    const sessionCookies = loginRes.headers.get("set-cookie") || cookies;

    // Check if login was successful (redirect to dashboard)
    if (loginRes.status === 302 || loginRes.status === 200) {
      return { cookies: sessionCookies, csrfToken };
    }

    console.error("Login failed with status:", loginRes.status);
    return null;
  } catch (error) {
    console.error("Login error:", error);
    return null;
  }
}

// Fetch a page with session
async function fetchWithSession(url: string, session: MeilandSession): Promise<string> {
  const res = await fetch(url, {
    headers: {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
      "Cookie": session.cookies,
    },
  });
  return res.text();
}

// Parse team page for players and next match
function parseTeamPage(html: string): { players: any[]; nextMatch: any | null } {
  const players: any[] = [];
  let nextMatch = null;

  // Extract players from roster table
  // Pattern: Look for player rows with stats
  const playerPattern = /<tr[^>]*>[\s\S]*?<td[^>]*>[\s\S]*?(?:player|jugador)[\s\S]*?<\/tr>/gi;
  const playerMatches = html.matchAll(playerPattern);

  // Extract player names and stats from table rows
  const tableRows = html.match(/<tr[^>]*class="[^"]*"[^>]*>[\s\S]*?<\/tr>/gi) || [];

  for (const row of tableRows) {
    // Try to extract player info
    const nameMatch = row.match(/<a[^>]*href="[^"]*player[^"]*"[^>]*>([^<]+)<\/a>/i);
    const statsMatch = row.match(/<td[^>]*>(\d+)<\/td>/gi);

    if (nameMatch && statsMatch) {
      const stats = statsMatch.map(s => parseInt(s.replace(/<[^>]+>/g, '')) || 0);
      players.push({
        name: nameMatch[1].trim(),
        games_played: stats[0] || 0,
        goals: stats[1] || 0,
        assists: stats[2] || 0,
      });
    }
  }

  // Extract next match info
  const nextMatchPattern = /pr[oó]ximo\s*partido[\s\S]*?<div[^>]*class="[^"]*match[^"]*"[^>]*>[\s\S]*?<\/div>/i;
  const nextMatchHtml = html.match(nextMatchPattern);

  if (nextMatchHtml) {
    const dateMatch = nextMatchHtml[0].match(/(\d{1,2}[\/-]\d{1,2}[\/-]\d{2,4})/);
    const timeMatch = nextMatchHtml[0].match(/(\d{1,2}:\d{2})/);
    const rivalMatch = nextMatchHtml[0].match(/vs\.?\s*([^<\n]+)/i);

    if (dateMatch || rivalMatch) {
      nextMatch = {
        date: dateMatch ? dateMatch[1] : null,
        time: timeMatch ? timeMatch[1] : null,
        rival: rivalMatch ? rivalMatch[1].trim() : "TBD",
        home: html.includes("Local") || html.includes("Casa"),
      };
    }
  }

  return { players, nextMatch };
}

// Parse division page for standings and calendar
function parseDivisionPage(html: string): { standings: any[]; matches: any[] } {
  const standings: any[] = [];
  const matches: any[] = [];

  // Extract standings table
  // Look for classification/standings section
  const standingsPattern = /<table[^>]*class="[^"]*(?:standings|clasificacion|table)[^"]*"[^>]*>[\s\S]*?<\/table>/i;
  const standingsTable = html.match(standingsPattern);

  if (standingsTable) {
    const rows = standingsTable[0].match(/<tr[^>]*>[\s\S]*?<\/tr>/gi) || [];

    for (let i = 1; i < rows.length; i++) { // Skip header row
      const cells = rows[i].match(/<td[^>]*>([\s\S]*?)<\/td>/gi) || [];
      if (cells.length >= 4) {
        const teamName = cells[1]?.replace(/<[^>]+>/g, '').trim() || '';
        const points = parseInt(cells[cells.length - 1]?.replace(/<[^>]+>/g, '')) || 0;
        const played = parseInt(cells[2]?.replace(/<[^>]+>/g, '')) || 0;
        const won = parseInt(cells[3]?.replace(/<[^>]+>/g, '')) || 0;
        const drawn = parseInt(cells[4]?.replace(/<[^>]+>/g, '')) || 0;
        const lost = parseInt(cells[5]?.replace(/<[^>]+>/g, '')) || 0;
        const gf = parseInt(cells[6]?.replace(/<[^>]+>/g, '')) || 0;
        const ga = parseInt(cells[7]?.replace(/<[^>]+>/g, '')) || 0;

        if (teamName) {
          standings.push({
            position: i,
            team_name: teamName,
            played,
            won,
            drawn,
            lost,
            goals_for: gf,
            goals_against: ga,
            goal_difference: gf - ga,
            points,
          });
        }
      }
    }
  }

  // Extract match calendar
  const matchPattern = /<div[^>]*class="[^"]*match[^"]*"[^>]*>[\s\S]*?<\/div>/gi;
  const matchDivs = html.matchAll(matchPattern);

  for (const match of matchDivs) {
    const dateMatch = match[0].match(/(\d{1,2}[\/-]\d{1,2}[\/-]\d{2,4})/);
    const teamsMatch = match[0].match(/([^<]+)\s*(?:vs\.?|-)\s*([^<]+)/);
    const scoreMatch = match[0].match(/(\d+)\s*-\s*(\d+)/);

    if (teamsMatch) {
      matches.push({
        date: dateMatch ? dateMatch[1] : null,
        home_team: teamsMatch[1].trim(),
        away_team: teamsMatch[2].trim(),
        home_score: scoreMatch ? parseInt(scoreMatch[1]) : null,
        away_score: scoreMatch ? parseInt(scoreMatch[2]) : null,
        played: !!scoreMatch,
      });
    }
  }

  return { standings, matches };
}

// Sync data to Supabase
async function syncToSupabase(data: {
  players: any[];
  standings: any[];
  matches: any[];
  nextMatch: any | null;
}) {
  const supabaseUrl = Deno.env.get("SUPABASE_URL") || "";
  const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";

  if (!supabaseUrl || !supabaseKey) {
    throw new Error("Supabase credentials not configured");
  }

  const supabase = createClient(supabaseUrl, supabaseKey);

  const results = {
    players: { updated: 0, errors: 0 },
    standings: { updated: 0, errors: 0 },
    matches: { updated: 0, errors: 0 },
  };

  // Sync players
  for (const player of data.players) {
    const { error } = await supabase
      .from("players")
      .upsert(
        {
          name: player.name,
          games_played: player.games_played,
          goals: player.goals,
          assists: player.assists,
          updated_at: new Date().toISOString(),
        },
        { onConflict: "name" }
      );

    if (error) {
      console.error("Player sync error:", error);
      results.players.errors++;
    } else {
      results.players.updated++;
    }
  }

  // Sync standings
  for (const standing of data.standings) {
    const { error } = await supabase
      .from("standings")
      .upsert(
        {
          ...standing,
          updated_at: new Date().toISOString(),
        },
        { onConflict: "team_name" }
      );

    if (error) {
      console.error("Standings sync error:", error);
      results.standings.errors++;
    } else {
      results.standings.updated++;
    }
  }

  // Sync matches
  for (const match of data.matches) {
    const { error } = await supabase
      .from("matches")
      .upsert(
        {
          date: match.date,
          opponent: match.home_team.includes("Madagascar") ? match.away_team : match.home_team,
          home_score: match.home_score,
          away_score: match.away_score,
          is_home: match.home_team.includes("Madagascar"),
          competition: "Liga Meiland",
          updated_at: new Date().toISOString(),
        },
        { onConflict: "date,opponent" }
      );

    if (error) {
      console.error("Match sync error:", error);
      results.matches.errors++;
    } else {
      results.matches.updated++;
    }
  }

  return results;
}

serve(async (req) => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    // Verify authorization (optional - add your own auth logic)
    const authHeader = req.headers.get("Authorization");
    // You can add API key validation here

    console.log("Starting Meiland sync...");

    // Step 1: Login to Meiland
    const session = await loginToMeiland();
    if (!session) {
      return new Response(
        JSON.stringify({ error: "Failed to login to Meiland" }),
        { status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    console.log("Logged in successfully");

    // Step 2: Fetch team page
    const teamHtml = await fetchWithSession(
      `${MEILAND_BASE}/app/team/view?id=${TEAM_ID}`,
      session
    );
    const { players, nextMatch } = parseTeamPage(teamHtml);

    console.log(`Found ${players.length} players`);

    // Step 3: Fetch division page
    const divisionHtml = await fetchWithSession(
      `${MEILAND_BASE}/app/division/view?id=${DIVISION_ID}`,
      session
    );
    const { standings, matches } = parseDivisionPage(divisionHtml);

    console.log(`Found ${standings.length} teams in standings, ${matches.length} matches`);

    // Step 4: Sync to Supabase
    const syncResults = await syncToSupabase({
      players,
      standings,
      matches,
      nextMatch,
    });

    return new Response(
      JSON.stringify({
        success: true,
        timestamp: new Date().toISOString(),
        data: {
          players: players.length,
          standings: standings.length,
          matches: matches.length,
          nextMatch,
        },
        sync: syncResults,
      }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  } catch (error) {
    console.error("Sync error:", error);
    return new Response(
      JSON.stringify({ error: error.message }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
