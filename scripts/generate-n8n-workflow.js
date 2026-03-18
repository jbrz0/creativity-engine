#!/usr/bin/env node
/**
 * Generates the n8n Creativity Engine workflow JSON.
 *
 * This script produces a complete, importable n8n workflow that replicates
 * the full creativity-engine pipeline:
 *   Telegram Input → Preprocess → 4 Parallel Agents → Synthesis →
 *   4 Parallel Critiques → Ensemble Score → Conditional Refinement → Telegram Output
 *
 * Models used (via OpenRouter):
 *   - Novelty Agent: Claude Opus 4 (temp 0.95) — most creative
 *   - Specialized Agent: Gemini 2.5 Pro (temp 0.7) — domain expertise
 *   - MiniCAE Agent: Gemini 2.0 Flash (temp 0.6) — fast/cheap analysis
 *   - IdeaCAE Agent: GPT-4.1 (temp 0.75) — structured thinking
 *   - Synthesis: Claude Opus 4 (temp 0.7) — best at merging
 *   - All 4 Critique agents: Gemini 2.0 Flash (temp 0.4-0.5) — cheap scoring
 *   - Refinement: Claude Opus 4 (temp 0.6) — quality polish
 *
 * Usage: node scripts/generate-n8n-workflow.js
 * Output: n8n-creativity-engine.json (importable into n8n)
 */

const fs = require('fs');
const path = require('path');

// =============================================================================
// CODE NODE SCRIPTS
// =============================================================================

// ---------- PREPROCESS & BUILD PROMPTS ----------
const preprocessCode = `
// ── Stopwords ──
const SW = new Set(['a','an','the','and','or','but','if','then','else','for','of','to','in','on','with','by','as','at','from','is','are','was','were','be','being','been','it','this','that','these','those','i','you','we','they','he','she','them','us','our','my','your','their','me','him','her','what','which','who','whom','about','into','over','under','between','within','without','can','could','should','would','may','might','will','shall','do','does','did','have','has','had','so','just','not','no','yes','also','very','really','much','more','most','some','any','all','each','every','own','such','only','other','than','too','even','well','back','still','way','take','come','make','like','long','look','many','get','use','know','want','say','see','try','one','two']);

// ── Serendipity Corpus (cross-domain inspiration seeds) ──
const CORPUS = [
  'Consider the role of entropy in information systems and how disorder creates new possibilities for order.',
  'Biological mimicry often yields robust engineering solutions—nature has had billions of years to optimize.',
  'Fractal patterns appear in both nature and data structures, suggesting self-similarity is a universal principle.',
  'The map is not the territory; the model is not the reality—what assumptions are you baking in?',
  'Feedback loops can stabilize or destabilize depending on delay, gain, and the observer.',
  'Constraint breeds creativity—the sonnet form produced Shakespeare\\'s greatest expressions of the human condition.',
  'Navigate the space between order and chaos—the edge of complexity is where emergence happens.',
  'Cross-pollination between unrelated fields has produced most of humanity\\'s breakthrough innovations.',
  'Invert every assumption and start from the opposite end—what would that look like?',
  'The adjacent possible defines what innovations can emerge next from the current state of knowledge.',
  'Negative space is as important as positive space—what\\'s missing tells you as much as what\\'s present.',
  'Systems thinking reveals that local optimizations often degrade global performance dramatically.',
  'Metaphors are not just literary devices; they are cognitive tools that shape how we frame and solve problems.',
  'Emergence occurs when simple rules interacting produce complex, unpredictable, and beautiful behaviors.',
  'The most creative solutions often come from misapplying a tool from one domain to an entirely different one.',
  'Tension between opposing forces (thesis/antithesis) often produces superior synthesis—dialectical creativity.',
  'Resilience comes not from rigidity but from adaptive flexibility, redundancy, and graceful degradation.',
  'What if time ran backwards? How would this process look in reverse? What would we notice first?',
  'The boundary between categories is often where the most interesting and novel phenomena occur.',
  'Stochastic resonance: sometimes adding noise actually improves signal detection and pattern recognition.',
  'Hofstadter\\'s law: it always takes longer than you expect, even when you account for Hofstadter\\'s law.',
  'The Pareto frontier reveals that optimizing one dimension necessarily trades off against others.',
  'Stigmergy—indirect coordination through environment modification—explains ant colonies and Wikipedia alike.',
  'What would a civilization that evolved underwater think about this problem differently?',
  'The strongest structures in nature use tension and compression in dynamic balance—tensegrity.',
  'Every expert was once a beginner who asked questions that seemed too simple to ask.',
  'Serendipity is not random—it favors the prepared mind that can recognize unexpected connections.',
  'The medium shapes the message: the tool you use to think literally changes what thoughts are possible.',
  'In complex adaptive systems, the agents and the environment co-evolve in unpredictable ways.',
  'What would this look like at 1000x scale? At 1/1000th scale? Scale reveals hidden structure.'
];

// ── Text Processing Functions ──
function normalize(t) {
  return t.replace(/\\r\\n/g, '\\n').replace(/\\r/g, '\\n').replace(/[ \\t]+/g, ' ').replace(/\\n{3,}/g, '\\n\\n').trim();
}

function extractKeywords(text, max = 40) {
  const freq = {};
  text.toLowerCase().split(/[^\\w\\-']+/).filter(w => w && w.length > 2 && !SW.has(w)).forEach(w => { freq[w] = (freq[w] || 0) + 1; });
  return Object.entries(freq).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, max).map(([w]) => w);
}

function extractSentences(text) {
  const s = text.split(/(?<=[.!?])\\s+/).filter(s => s.trim());
  return s.length > 0 ? s : [text];
}

function cooccurrencePairs(sentences, keywords, maxPairs = 200) {
  const ks = new Set(keywords);
  const pairs = [];
  for (const s of sentences) {
    const present = [...new Set(s.toLowerCase().split(/[^\\w\\-']+/).filter(w => ks.has(w)))];
    for (let i = 0; i < present.length; i++) {
      for (let j = i + 1; j < present.length; j++) {
        if (present[i] !== present[j]) {
          pairs.push([present[i], present[j]]);
          if (pairs.length >= maxPairs) return pairs;
        }
      }
    }
  }
  return pairs;
}

// ── Graph Element Extraction (keyword-based, no spaCy needed) ──
function extractGraphElements(keywords, pairs) {
  const nodes = [...new Set(keywords)].slice(0, 160);
  const rels = pairs.slice(0, 240).map(([a, b]) => ({ src: a, rel: 'RELATED', dst: b }));
  const nodeSet = new Set(nodes.map(n => n.toLowerCase()));
  for (const r of rels) {
    if (!nodeSet.has(r.src.toLowerCase())) { nodeSet.add(r.src.toLowerCase()); nodes.push(r.src); }
    if (!nodeSet.has(r.dst.toLowerCase())) { nodeSet.add(r.dst.toLowerCase()); nodes.push(r.dst); }
  }
  return { nodes: nodes.slice(0, 160), relationships: rels.slice(0, 240) };
}

// ── Creativity Control Mapping (port of controls.py) ──
function sliderToBand(value, minB = 1, maxB = 10) {
  const v = Math.max(0, Math.min(100, value));
  return Math.floor(minB + ((maxB - minB) * (v / 100)));
}

function mapSliders(randomness, speculation, ideas) {
  // Randomness → Sampling parameters
  const randBand = sliderToBand(randomness, 1, 10);
  let temp = 0.6 + (0.6 * ((randBand - 1) / 9));
  temp = Math.min(1.2, Math.max(0.1, temp));
  const top_p = Math.min(0.99, 0.85 + (0.14 * (randomness / 100)));
  const presence_penalty = 0.5 * (randomness / 100);
  const frequency_penalty = 0.5 * (randomness / 100);

  // Speculation → Branches/Layers
  const specBand = sliderToBand(speculation, 1, 10);
  let branches = 1, layers = 1;
  if (specBand > 3) branches = 2;
  if (specBand > 6) { branches = 3; layers = 2; }
  if (specBand > 8) { branches = 4; layers = 2; }

  // Ideas → Count/Density
  const ideaCount = sliderToBand(ideas, 3, 15);
  const convergeBias = 1.0 - (ideas / 100);
  const seedsCount = sliderToBand(Math.floor((randomness + speculation) / 2), 0, 8);
  let graphHops = 1;
  if (speculation > 50) graphHops = 2;
  if (speculation > 80) graphHops = 3;

  return {
    sampling: { temperature: temp, top_p, presence_penalty, frequency_penalty },
    kernel: { branches, layers, ideaCount, convergeBias, seedsCount, graphHops }
  };
}

// ── Serendipity Seeds (word-overlap heuristic) ──
function getSeeds(prompt, k) {
  if (k <= 0) return [];
  const toks = new Set((prompt.toLowerCase().match(/[a-z0-9-]+/g) || []).filter(w => w.length > 2));
  const scored = CORPUS.map(line => {
    const words = new Set((line.toLowerCase().match(/[a-z0-9-]+/g) || []).filter(w => w.length > 2));
    let overlap = 0;
    for (const t of toks) if (words.has(t)) overlap++;
    return { score: overlap, line };
  });
  scored.sort((a, b) => b.score - a.score);
  if (scored[0] && scored[0].score <= 0) {
    // Shuffle if no overlap
    for (let i = scored.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [scored[i], scored[j]] = [scored[j], scored[i]];
    }
  }
  return scored.slice(0, k).map(s => s.line);
}

// ── Graph Insights Formatting ──
function formatInsights(graph, maxSeeds = 5) {
  const parts = [];
  // Use keyword frequency as importance proxy
  const topNodes = graph.nodes.slice(0, maxSeeds);
  if (topNodes.length) parts.push('- Central concepts: ' + topNodes.join(', '));
  const bridges = graph.relationships.slice(0, maxSeeds).map(r => r.src + ' ↔ ' + r.dst);
  if (bridges.length) parts.push('- Bridge paths: ' + bridges.join(', '));
  parts.push('- Graph size: ' + graph.nodes.length + ' nodes, ' + graph.relationships.length + ' edges');
  return parts.join('\\n');
}

// ══════════════════════════════════════════════
// MAIN PROCESSING
// ══════════════════════════════════════════════
const inputText = $input.first().json.message?.text || $input.first().json.text || '';
const chatId = $input.first().json.message?.chat?.id || $input.first().json.chat_id || '';

// 1. Preprocess
const cleaned = normalize(inputText);
const sentences = extractSentences(cleaned);
const keywords = extractKeywords(cleaned, 40);
const pairs = cooccurrencePairs(sentences, keywords);
const graph = extractGraphElements(keywords, pairs);

// 2. Map creativity controls (high creativity defaults)
const randomness = 85, speculation = 90, ideas = 80;
const params = mapSliders(randomness, speculation, ideas);

// 3. Generate seeds & insights
const seeds = getSeeds(cleaned, params.kernel.seedsCount);
const insights = formatInsights(graph, 5);

// ══════════════════════════════════════════════
// BUILD AGENT PROMPTS
// ══════════════════════════════════════════════

// ── Shared creative config injection ──
function creativeSuffix() {
  let s = '';
  if (seeds.length) s += '\\n\\nSerendipity Seeds (use as random cross-domain stimuli):\\n' + seeds.join('\\n');
  if (insights) s += '\\n\\nGraph Insights:\\n' + insights;
  if (speculation > 60) s += '\\n\\nApply HIGH SPECULATION: Take bold creative risks. Ignore conventional constraints.';
  if (params.kernel.branches > 1) s += '\\n\\nExplore at least ' + params.kernel.branches + ' distinct What-if scenarios or stochastic branches.';
  return s;
}

// ── NOVELTY AGENT (Claude Opus 4, temp 0.95) ──
const noveltySystem = 'You are a Novelty Agent in an advanced creativity engine. Your purpose is to generate highly novel, unexpected, and creative ideas.\\n\\nCore principles:\\n- Push boundaries and explore unconventional combinations\\n- Break patterns and challenge assumptions\\n- Generate surprising connections and analogies\\n- Prioritize originality over convention\\n- Think laterally and divergently\\n\\nWhen generating ideas:\\n1. Identify unexpected connections\\n2. Combine disparate concepts\\n3. Invert common assumptions\\n4. Explore metaphorical spaces\\n5. Generate multiple novel angles\\n\\nFormat your response as JSON:\\n{\\n  \"ideas\": [\"idea1\", \"idea2\", \"idea3\"],\\n  \"novel_connections\": [\"connection1\", \"connection2\"],\\n  \"confidence\": 0.85,\\n  \"reasoning\": \"Brief explanation of your creative process\"\\n}';

const noveltyUser = 'Generate highly novel and creative ideas based on this input:\\n\\nInput: ' + cleaned + creativeSuffix() + '\\n\\nGenerate multiple novel ideas and unexpected connections.';

// ── SPECIALIZED AGENT (Gemini 2.5 Pro, temp 0.7) ──
const specializedSystem = 'You are a Specialized Agent in an advanced creativity engine. Your purpose is to provide expert, domain-focused creative insights.\\n\\nCore principles:\\n- Apply deep domain knowledge\\n- Use field-specific techniques and conventions\\n- Reference relevant precedents and examples\\n- Balance creativity with domain expertise\\n- Provide technically sound suggestions\\n\\nWhen processing:\\n1. Identify domain-specific patterns\\n2. Apply relevant techniques\\n3. Reference field conventions\\n4. Suggest expert-level refinements\\n5. Consider audience and context\\n\\nFormat your response as JSON:\\n{\\n  \"analysis\": \"Domain-specific analysis\",\\n  \"suggestions\": [\"suggestion1\", \"suggestion2\", \"suggestion3\"],\\n  \"techniques\": [\"technique1\", \"technique2\"],\\n  \"confidence\": 0.85,\\n  \"reasoning\": \"Brief explanation\"\\n}';

const specializedUser = 'Provide expert, domain-focused creative analysis and suggestions:\\n\\nDomain: general creative\\nInput: ' + cleaned + '\\n\\nProvide domain-specific analysis, techniques, and suggestions.';

// ── MINI-CAE AGENT (Gemini 2.0 Flash, temp 0.6) ──
const miniCaeSystem = 'You are a Mini-CAE (Creative Analysis and Enhancement) Agent in an advanced creativity engine. Your purpose is to provide focused, rapid creative analysis and enhancement.\\n\\nCore principles:\\n- Quick, actionable insights\\n- Focus on immediate improvements\\n- Identify key strengths and weaknesses\\n- Suggest specific enhancements\\n- Maintain creative momentum\\n\\nWhen analyzing:\\n1. Identify core creative elements\\n2. Highlight strengths\\n3. Spot improvement opportunities\\n4. Suggest specific enhancements\\n5. Maintain original intent\\n\\nFormat your response as JSON:\\n{\\n  \"strengths\": [\"strength1\", \"strength2\"],\\n  \"opportunities\": [\"opportunity1\", \"opportunity2\"],\\n  \"enhancements\": [\"enhancement1\", \"enhancement2\"],\\n  \"confidence\": 0.85,\\n  \"reasoning\": \"Brief explanation\"\\n}';

const miniCaeUser = 'Analyze this creative content and suggest enhancements:\\n\\nContent: ' + cleaned + '\\n\\nProvide:\\n1. Key strengths of this content\\n2. Opportunities for improvement\\n3. Specific enhancement suggestions';

// ── IDEA-CAE AGENT (GPT-4.1, temp 0.75) ──
const ideaCaeSystem = 'You are an Idea-CAE (Creative Analysis and Enhancement) Agent in an advanced creativity engine. Your purpose is to deeply develop and enhance creative ideas.\\n\\nCore principles:\\n- Comprehensive idea exploration\\n- Multi-dimensional development\\n- Consider implications and variations\\n- Build depth and richness\\n- Maintain creative coherence\\n\\nWhen developing ideas:\\n1. Expand the core concept\\n2. Explore multiple dimensions\\n3. Consider variations and alternatives\\n4. Develop supporting elements\\n5. Create implementation pathways\\n\\nFormat your response as JSON:\\n{\\n  \"core_concept\": \"Refined core idea\",\\n  \"dimensions\": [\"dimension1\", \"dimension2\", \"dimension3\"],\\n  \"variations\": [\"variation1\", \"variation2\"],\\n  \"supporting_elements\": [\"element1\", \"element2\"],\\n  \"implementation\": [\"step1\", \"step2\"],\\n  \"confidence\": 0.85,\\n  \"reasoning\": \"Brief explanation\"\\n}';

let ideaCaeUser = 'Comprehensively develop and enhance this creative idea:\\n\\nIdea: ' + cleaned;
ideaCaeUser += '\\n\\nContext Controls:\\n- Idea Density Target: ' + ideas + '/100\\n- Speculation Level: ' + speculation + '/100';
if (ideas > 70) ideaCaeUser += '\\n\\nREQUIREMENT: Provide EXTREME depth. Drill down into 5+ dimensions and implementation details.';
if (speculation > 75) ideaCaeUser += '\\n\\nREQUIREMENT: Include What-If scenarios that challenge the core premise of the idea.';
ideaCaeUser += '\\n\\nProvide comprehensive idea development including dimensions, variations, and implementation.';

// ══════════════════════════════════════════════
// BUILD HTTP REQUEST BODIES
// ══════════════════════════════════════════════
const noveltyBody = {
  model: 'anthropic/claude-opus-4',
  messages: [{ role: 'system', content: noveltySystem }, { role: 'user', content: noveltyUser }],
  temperature: Math.min(1.2, params.sampling.temperature + 0.15),
  top_p: params.sampling.top_p,
  presence_penalty: params.sampling.presence_penalty,
  frequency_penalty: params.sampling.frequency_penalty,
  max_tokens: 4096
};

const specializedBody = {
  model: 'google/gemini-2.5-pro',
  messages: [{ role: 'system', content: specializedSystem }, { role: 'user', content: specializedUser }],
  temperature: 0.7,
  max_tokens: 4096
};

const miniCaeBody = {
  model: 'google/gemini-2.0-flash-001',
  messages: [{ role: 'system', content: miniCaeSystem }, { role: 'user', content: miniCaeUser }],
  temperature: 0.6,
  max_tokens: 4096
};

const ideaCaeBody = {
  model: 'openai/gpt-4.1',
  messages: [{ role: 'system', content: ideaCaeSystem }, { role: 'user', content: ideaCaeUser }],
  temperature: Math.max(0.4, params.sampling.temperature - 0.1),
  max_tokens: 4096
};

return [{
  json: {
    chatId,
    originalInput: inputText,
    cleaned,
    keywords,
    seeds,
    insights,
    sampling: params.sampling,
    kernel: params.kernel,
    noveltyBody,
    specializedBody,
    miniCaeBody,
    ideaCaeBody
  }
}];
`;

// ---------- BUILD SYNTHESIS PROMPT ----------
const buildSynthesisCode = `
// Extract agent responses from the 4 merged inputs
const items = $input.all();
const agentOutputs = [];

for (const item of items) {
  try {
    const data = item.json;
    // Handle both raw HTTP response and parsed JSON
    let content = '';
    let agentName = 'Unknown';

    if (data.choices && data.choices[0]) {
      content = data.choices[0].message.content;
    } else if (data.data && data.data.choices) {
      content = data.data.choices[0].message.content;
    } else if (data.content) {
      content = data.content;
    } else {
      content = JSON.stringify(data).substring(0, 2000);
    }

    // Try to parse JSON from the content
    let parsed = null;
    try {
      // Sometimes models wrap JSON in markdown code blocks
      const jsonMatch = content.match(/\\\`\\\`\\\`json?\\n?([\\s\\S]*?)\\\`\\\`\\\`/);
      const toParse = jsonMatch ? jsonMatch[1] : content;
      parsed = JSON.parse(toParse);
    } catch (e) {
      parsed = null;
    }

    // Determine agent from the model used or content structure
    if (parsed) {
      if (parsed.ideas) agentName = 'NoveltyAgent';
      else if (parsed.analysis && parsed.techniques) agentName = 'SpecializedAgent';
      else if (parsed.strengths && parsed.enhancements) agentName = 'MiniCAEAgent';
      else if (parsed.core_concept) agentName = 'IdeaCAEAgent';
    }

    // Format content for synthesis
    let formatted = content;
    if (parsed) {
      if (parsed.ideas) {
        formatted = 'Novel Ideas:\\n' + parsed.ideas.map(i => '- ' + i).join('\\n');
        if (parsed.novel_connections) formatted += '\\n\\nNovel Connections:\\n' + parsed.novel_connections.map(c => '- ' + c).join('\\n');
      } else if (parsed.analysis) {
        formatted = 'Domain Analysis:\\n' + parsed.analysis + '\\n\\nSuggestions:\\n' + (parsed.suggestions || []).map(s => '- ' + s).join('\\n');
        if (parsed.techniques) formatted += '\\n\\nTechniques:\\n' + parsed.techniques.map(t => '- ' + t).join('\\n');
      } else if (parsed.strengths) {
        formatted = 'Strengths:\\n' + parsed.strengths.map(s => '- ' + s).join('\\n');
        formatted += '\\n\\nOpportunities:\\n' + (parsed.opportunities || []).map(o => '- ' + o).join('\\n');
        formatted += '\\n\\nEnhancements:\\n' + (parsed.enhancements || []).map(e => '- ' + e).join('\\n');
      } else if (parsed.core_concept) {
        formatted = 'Core Concept:\\n' + parsed.core_concept;
        formatted += '\\n\\nDimensions:\\n' + (parsed.dimensions || []).map(d => '- ' + d).join('\\n');
        if (parsed.variations) formatted += '\\n\\nVariations:\\n' + parsed.variations.map(v => '- ' + v).join('\\n');
        if (parsed.implementation) formatted += '\\n\\nImplementation:\\n' + parsed.implementation.map((s, i) => (i + 1) + '. ' + s).join('\\n');
      }
    }

    const confidence = parsed?.confidence || 0.7;
    agentOutputs.push({ agentName, content: formatted, confidence });
  } catch (e) {
    // Skip failed agent outputs
  }
}

// Get original input from the preprocess node
const originalInput = $('Preprocess & Build Prompts').item.json.originalInput;
const chatId = $('Preprocess & Build Prompts').item.json.chatId;

// Build synthesis prompt
const outputsText = agentOutputs.map(a =>
  '[' + a.agentName + '] (Confidence: ' + a.confidence.toFixed(2) + ')\\n' + a.content
).join('\\n\\n---\\n\\n');

const synthSystem = 'You are an expert at synthesizing creative outputs into cohesive, polished results. You take the best ideas from multiple creative agents and weave them into a unified, rich, and actionable output.';

const synthUser = 'Synthesize these creative outputs into a comprehensive, cohesive result:\\n\\n' + outputsText + '\\n\\nCreate a synthesis that:\\n1. Incorporates the best ideas from each agent\\n2. Maintains creative coherence and flow\\n3. Builds depth and richness—go deep, not shallow\\n4. Resolves any conflicts or redundancies elegantly\\n5. Produces a polished, unified creative output that is MORE than the sum of its parts\\n\\nProvide the synthesized creative output:';

const synthesisBody = {
  model: 'anthropic/claude-opus-4',
  messages: [
    { role: 'system', content: synthSystem },
    { role: 'user', content: synthUser }
  ],
  temperature: 0.7,
  max_tokens: 8192
};

return [{
  json: {
    chatId,
    originalInput,
    agentOutputs,
    synthesisBody
  }
}];
`;

// ---------- BUILD CRITIQUE PROMPTS ----------
const buildCritiqueCode = `
// Extract synthesis output
const synthResponse = $input.first().json;
let synthesized = '';
if (synthResponse.choices && synthResponse.choices[0]) {
  synthesized = synthResponse.choices[0].message.content;
} else if (synthResponse.data && synthResponse.data.choices) {
  synthesized = synthResponse.data.choices[0].message.content;
} else {
  synthesized = JSON.stringify(synthResponse).substring(0, 4000);
}

const originalInput = $('Build Synthesis Prompt').item.json.originalInput;
const chatId = $('Build Synthesis Prompt').item.json.chatId;

// ── NOVELTY CRITIQUE ──
const noveltySys = 'You are a Novelty Critique Agent. Evaluate the novelty, originality, and uniqueness of creative outputs.\\n\\nEvaluation criteria: Originality, Unexpectedness, Pattern breaking, Fresh perspective, Innovation.\\n\\nFormat response as JSON:\\n{\\n  \"novelty_score\": 0.85,\\n  \"novel_elements\": [\"element1\"],\\n  \"suggestions\": [\"suggestion1\"],\\n  \"confidence\": 0.9\\n}';
const noveltyUser = 'Evaluate the novelty and originality of this creative output:\\n\\nContent to evaluate: ' + synthesized + '\\n\\nOriginal input: ' + originalInput + '\\n\\nProvide a comprehensive novelty evaluation with score and suggestions.';

// ── COHERENCE CRITIQUE ──
const coherenceSys = 'You are a Coherence Critique Agent. Evaluate the logical consistency, flow, and internal coherence of creative outputs.\\n\\nEvaluation criteria: Internal consistency, Logical flow, Structural integrity, Clarity, Unity.\\n\\nFormat response as JSON:\\n{\\n  \"coherence_score\": 0.85,\\n  \"strengths\": [\"strength1\"],\\n  \"inconsistencies\": [\"issue1\"],\\n  \"suggestions\": [\"suggestion1\"],\\n  \"confidence\": 0.9\\n}';
const coherenceUser = 'Evaluate the coherence, consistency, and logical flow of this creative output:\\n\\nContent to evaluate: ' + synthesized + '\\n\\nProvide a comprehensive coherence evaluation with score and suggestions.';

// ── RELEVANCE CRITIQUE ──
const relevanceSys = 'You are a Relevance Critique Agent. Evaluate how well creative outputs address the input, goals, and context.\\n\\nEvaluation criteria: Input alignment, Goal fulfillment, Context appropriateness, Practical applicability.\\n\\nFormat response as JSON:\\n{\\n  \"relevance_score\": 0.85,\\n  \"aligned_elements\": [\"element1\"],\\n  \"divergences\": [\"gap1\"],\\n  \"suggestions\": [\"suggestion1\"],\\n  \"confidence\": 0.9\\n}';
const relevanceUser = 'Evaluate the relevance of this creative output to the original input:\\n\\nContent to evaluate: ' + synthesized + '\\n\\nOriginal input: ' + originalInput + '\\n\\nProvide a comprehensive relevance evaluation with score and suggestions.';

// ── PERSONALIZATION CRITIQUE ──
const personalSys = 'You are a Personalized Critique Agent. Evaluate how well creative outputs match quality standards, engagement, and depth.\\n\\nEvaluation criteria: Depth of insight, Engagement quality, Actionability, Tone appropriateness, Personal resonance.\\n\\nFormat response as JSON:\\n{\\n  \"personalization_score\": 0.85,\\n  \"style_matches\": [\"match1\"],\\n  \"suggestions\": [\"suggestion1\"],\\n  \"confidence\": 0.9\\n}';
const personalUser = 'Evaluate the quality, depth, and engagement of this creative output:\\n\\nContent to evaluate: ' + synthesized + '\\n\\nProvide a comprehensive quality evaluation with score and suggestions.';

const critiqueModel = 'google/gemini-2.0-flash-001';

return [{
  json: {
    chatId,
    originalInput,
    synthesized,
    noveltyCritiqueBody: {
      model: critiqueModel,
      messages: [{ role: 'system', content: noveltySys }, { role: 'user', content: noveltyUser }],
      temperature: 0.5, max_tokens: 2048
    },
    coherenceCritiqueBody: {
      model: critiqueModel,
      messages: [{ role: 'system', content: coherenceSys }, { role: 'user', content: coherenceUser }],
      temperature: 0.4, max_tokens: 2048
    },
    relevanceCritiqueBody: {
      model: critiqueModel,
      messages: [{ role: 'system', content: relevanceSys }, { role: 'user', content: relevanceUser }],
      temperature: 0.4, max_tokens: 2048
    },
    personalCritiqueBody: {
      model: critiqueModel,
      messages: [{ role: 'system', content: personalSys }, { role: 'user', content: personalUser }],
      temperature: 0.5, max_tokens: 2048
    }
  }
}];
`;

// ---------- CALCULATE ENSEMBLE SCORE ----------
const ensembleScoreCode = `
// Parse all 4 critique responses
const items = $input.all();

function parseScore(item, scoreKey) {
  try {
    let content = '';
    const data = item.json;
    if (data.choices && data.choices[0]) content = data.choices[0].message.content;
    else if (data.data && data.data.choices) content = data.data.choices[0].message.content;
    else content = JSON.stringify(data);

    // Try to parse JSON
    const jsonMatch = content.match(/\\\`\\\`\\\`json?\\n?([\\s\\S]*?)\\\`\\\`\\\`/);
    const toParse = jsonMatch ? jsonMatch[1] : content;
    const parsed = JSON.parse(toParse);
    return {
      score: parsed[scoreKey] || 0.5,
      suggestions: parsed.suggestions || [],
      raw: content
    };
  } catch (e) {
    // Fallback: try to extract score with regex
    try {
      const content = item.json?.choices?.[0]?.message?.content || JSON.stringify(item.json);
      const match = content.match(new RegExp(scoreKey + '.*?([0-9]\\\\.[0-9]+)'));
      return { score: match ? parseFloat(match[1]) : 0.5, suggestions: [], raw: content };
    } catch (e2) {
      return { score: 0.5, suggestions: [], raw: '' };
    }
  }
}

const novelty = parseScore(items[0], 'novelty_score');
const coherence = parseScore(items[1], 'coherence_score');
const relevance = parseScore(items[2], 'relevance_score');
const personal = parseScore(items[3], 'personalization_score');

// Weighted ensemble score (matching original weights)
const ensembleScore = (
  0.30 * novelty.score +
  0.25 * coherence.score +
  0.30 * relevance.score +
  0.15 * personal.score
);

const needsRefinement = ensembleScore < 0.6;

// Collect all suggestions for potential refinement
const allSuggestions = [
  ...novelty.suggestions,
  ...coherence.suggestions,
  ...relevance.suggestions,
  ...personal.suggestions
].filter((s, i, arr) => arr.indexOf(s) === i).slice(0, 10);

const originalInput = $('Build Critique Prompts').item.json.originalInput;
const chatId = $('Build Critique Prompts').item.json.chatId;
const synthesized = $('Build Critique Prompts').item.json.synthesized;

return [{
  json: {
    chatId,
    originalInput,
    synthesized,
    scores: {
      novelty: novelty.score,
      coherence: coherence.score,
      relevance: relevance.score,
      personalization: personal.score
    },
    ensembleScore,
    needsRefinement,
    suggestions: allSuggestions
  }
}];
`;

// ---------- BUILD REFINEMENT PROMPT ----------
const buildRefinementCode = `
const data = $input.first().json;

const scoresText = Object.entries(data.scores).map(([k, v]) => '- ' + k + ': ' + v.toFixed(2)).join('\\n');
const suggestionsText = data.suggestions.map(s => '- ' + s).join('\\n');

const refineSystem = 'You are an expert at refining creative outputs based on structured critique. You improve weak areas while preserving and enhancing strengths.';

const refineUser = 'Refine this creative output based on the critique:\\n\\nOriginal Input: ' + data.originalInput + '\\n\\nCurrent Output:\\n' + data.synthesized + '\\n\\nCritique Scores:\\n' + scoresText + '\\n\\nEnsemble Score: ' + data.ensembleScore.toFixed(2) + ' (threshold: 0.60)\\n\\nSuggestions for Improvement:\\n' + suggestionsText + '\\n\\nCreate a refined version that:\\n1. Addresses the critique suggestions\\n2. Improves weak scoring areas\\n3. Maintains or enhances strengths\\n4. Preserves the core creative vision\\n5. Produces a more polished, deeper result\\n\\nProvide the refined output:';

return [{
  json: {
    chatId: data.chatId,
    originalInput: data.originalInput,
    refinementBody: {
      model: 'anthropic/claude-opus-4',
      messages: [
        { role: 'system', content: refineSystem },
        { role: 'user', content: refineUser }
      ],
      temperature: 0.6,
      max_tokens: 8192
    }
  }
}];
`;

// ---------- FORMAT REFINED OUTPUT ----------
const formatRefinedCode = `
const httpResponse = $input.first().json;
let refined = '';
if (httpResponse.choices && httpResponse.choices[0]) {
  refined = httpResponse.choices[0].message.content;
} else if (httpResponse.data && httpResponse.data.choices) {
  refined = httpResponse.data.choices[0].message.content;
} else {
  refined = JSON.stringify(httpResponse).substring(0, 4000);
}

const chatId = $('Build Refinement Prompt').item.json.chatId;
const ensembleData = $('Calculate Ensemble Score').item.json;

// Format for Telegram (Markdown)
let output = refined;
output += '\\n\\n---\\n_Creativity Engine • Refined (score: ' + ensembleData.ensembleScore.toFixed(2) + ' → improved)_';
output += '\\n_Models: Opus 4 + Gemini 2.5 Pro + GPT-4.1 + Flash_';

return [{ json: { chatId, finalOutput: output } }];
`;

// ---------- FORMAT DIRECT OUTPUT ----------
const formatDirectCode = `
const data = $input.first().json;

// Format for Telegram (Markdown)
let output = data.synthesized;
output += '\\n\\n---\\n_Creativity Engine • Score: ' + data.ensembleScore.toFixed(2) + '_';
output += '\\n_Models: Opus 4 + Gemini 2.5 Pro + GPT-4.1 + Flash_';

return [{ json: { chatId: data.chatId, finalOutput: output } }];
`;

// =============================================================================
// WORKFLOW STRUCTURE
// =============================================================================

function makeHttpRequestNode(id, name, position, bodyExpression, onError = 'continueRegularOutput') {
  return {
    parameters: {
      method: 'POST',
      url: 'https://openrouter.ai/api/v1/chat/completions',
      authentication: 'genericCredentialType',
      genericAuthType: 'httpHeaderAuth',
      sendHeaders: true,
      headerParameters: {
        parameters: [
          { name: 'HTTP-Referer', value: 'https://creativity-engine.n8n.local' },
          { name: 'X-Title', value: 'Creativity Engine' }
        ]
      },
      sendBody: true,
      specifyBody: 'json',
      jsonBody: bodyExpression,
      options: {
        timeout: 120000
      }
    },
    id,
    name,
    type: 'n8n-nodes-base.httpRequest',
    typeVersion: 4.2,
    position,
    onError,
    credentials: {
      httpHeaderAuth: {
        id: 'openrouter-api',
        name: 'OpenRouter API'
      }
    }
  };
}

function makeCodeNode(id, name, position, jsCode) {
  return {
    parameters: {
      mode: 'runOnceForAllItems',
      jsCode
    },
    id,
    name,
    type: 'n8n-nodes-base.code',
    typeVersion: 2,
    position
  };
}

const workflow = {
  name: 'Creativity Engine',
  nodes: [
    // ── SETUP NOTES ──
    {
      parameters: {
        content: `## 🧠 Creativity Engine — n8n Workflow\n\n### Setup Instructions\n\n1. **Telegram Bot**: Create a bot via @BotFather, get the token\n2. **Telegram Credential**: Create a "Telegram API" credential in n8n with your bot token\n3. **OpenRouter API Key**: Get one from https://openrouter.ai/keys\n4. **Header Auth Credential**: Create an "HTTP Header Auth" credential:\n   - **Name**: \`Authorization\`\n   - **Value**: \`Bearer YOUR_OPENROUTER_API_KEY\`\n   - Name the credential "OpenRouter API"\n\n### Pipeline Flow\n\`\`\`\nTelegram → Preprocess & Build Prompts\n  → 4 Parallel Creative Agents (Opus 4, Gemini 2.5 Pro, GPT-4.1, Flash)\n  → Synthesis (Opus 4)\n  → 4 Parallel Critique Agents (Flash)\n  → Ensemble Scoring\n  → Conditional Refinement (Opus 4, if score < 0.6)\n  → Telegram Response\n\`\`\`\n\n### Models (via OpenRouter)\n- **NoveltyAgent**: anthropic/claude-opus-4 (temp ~0.95)\n- **SpecializedAgent**: google/gemini-2.5-pro (temp 0.7)\n- **MiniCAEAgent**: google/gemini-2.0-flash-001 (temp 0.6)\n- **IdeaCAEAgent**: openai/gpt-4.1 (temp 0.75)\n- **Synthesis & Refinement**: anthropic/claude-opus-4\n- **All Critiques**: google/gemini-2.0-flash-001\n\n### Creativity Controls (hardcoded high)\n- Randomness: 85/100 → temp ~1.1, diverse sampling\n- Speculation: 90/100 → 4 what-if branches, 2 layers deep\n- Ideas: 80/100 → ~12 ideas, low convergence bias`
      },
      id: 'setup-note',
      name: 'Setup Instructions',
      type: 'n8n-nodes-base.stickyNote',
      typeVersion: 1,
      position: [-400, -100]
    },

    // ── 1. TELEGRAM TRIGGER ──
    {
      parameters: {
        updates: ['message'],
        additionalFields: {}
      },
      id: 'telegram-trigger',
      name: 'Telegram Trigger',
      type: 'n8n-nodes-base.telegramTrigger',
      typeVersion: 1.1,
      position: [0, 300],
      webhookId: 'creativity-engine-webhook',
      credentials: {
        telegramApi: {
          id: 'telegram-bot',
          name: 'Telegram Bot'
        }
      }
    },

    // ── 2. PREPROCESS & BUILD PROMPTS ──
    makeCodeNode('preprocess', 'Preprocess & Build Prompts', [280, 300], preprocessCode),

    // ── 3-6. CREATIVE AGENTS (parallel) ──
    makeHttpRequestNode(
      'novelty-agent', 'Novelty Agent (Opus 4)', [580, 40],
      "={{ JSON.stringify($json.noveltyBody) }}"
    ),
    makeHttpRequestNode(
      'specialized-agent', 'Specialized Agent (Gemini 2.5 Pro)', [580, 220],
      "={{ JSON.stringify($json.specializedBody) }}"
    ),
    makeHttpRequestNode(
      'minicae-agent', 'MiniCAE Agent (Flash)', [580, 400],
      "={{ JSON.stringify($json.miniCaeBody) }}"
    ),
    makeHttpRequestNode(
      'ideacae-agent', 'IdeaCAE Agent (GPT-4.1)', [580, 580],
      "={{ JSON.stringify($json.ideaCaeBody) }}"
    ),

    // ── 7. MERGE AGENT OUTPUTS ──
    {
      parameters: {
        mode: 'append',
        options: {}
      },
      id: 'merge-agents',
      name: 'Merge Agent Outputs',
      type: 'n8n-nodes-base.merge',
      typeVersion: 3,
      position: [860, 300]
    },

    // ── 8. BUILD SYNTHESIS PROMPT ──
    makeCodeNode('build-synthesis', 'Build Synthesis Prompt', [1080, 300], buildSynthesisCode),

    // ── 9. SYNTHESIS CALL ──
    makeHttpRequestNode(
      'synthesis-call', 'Synthesis (Opus 4)', [1320, 300],
      "={{ JSON.stringify($json.synthesisBody) }}"
    ),

    // ── 10. BUILD CRITIQUE PROMPTS ──
    makeCodeNode('build-critique', 'Build Critique Prompts', [1560, 300], buildCritiqueCode),

    // ── 11-14. CRITIQUE AGENTS (parallel) ──
    makeHttpRequestNode(
      'novelty-critique', 'Novelty Critique (Flash)', [1840, 40],
      "={{ JSON.stringify($json.noveltyCritiqueBody) }}"
    ),
    makeHttpRequestNode(
      'coherence-critique', 'Coherence Critique (Flash)', [1840, 220],
      "={{ JSON.stringify($json.coherenceCritiqueBody) }}"
    ),
    makeHttpRequestNode(
      'relevance-critique', 'Relevance Critique (Flash)', [1840, 400],
      "={{ JSON.stringify($json.relevanceCritiqueBody) }}"
    ),
    makeHttpRequestNode(
      'personal-critique', 'Personalization Critique (Flash)', [1840, 580],
      "={{ JSON.stringify($json.personalCritiqueBody) }}"
    ),

    // ── 15. MERGE CRITIQUE OUTPUTS ──
    {
      parameters: {
        mode: 'append',
        options: {}
      },
      id: 'merge-critiques',
      name: 'Merge Critique Outputs',
      type: 'n8n-nodes-base.merge',
      typeVersion: 3,
      position: [2120, 300]
    },

    // ── 16. CALCULATE ENSEMBLE SCORE ──
    makeCodeNode('ensemble-score', 'Calculate Ensemble Score', [2340, 300], ensembleScoreCode),

    // ── 17. IF NEEDS REFINEMENT ──
    {
      parameters: {
        conditions: {
          options: {
            caseSensitive: true,
            leftValue: '',
            typeValidation: 'strict'
          },
          conditions: [
            {
              id: 'refine-check',
              leftValue: '={{ $json.needsRefinement }}',
              rightValue: true,
              operator: {
                type: 'boolean',
                operation: 'equals',
                singleValue: true
              }
            }
          ],
          combinator: 'and'
        },
        options: {}
      },
      id: 'if-refine',
      name: 'Needs Refinement?',
      type: 'n8n-nodes-base.if',
      typeVersion: 2,
      position: [2580, 300]
    },

    // ── 18. BUILD REFINEMENT PROMPT (true path) ──
    makeCodeNode('build-refine', 'Build Refinement Prompt', [2820, 420], buildRefinementCode),

    // ── 19. REFINEMENT CALL ──
    makeHttpRequestNode(
      'refine-call', 'Refinement (Opus 4)', [3060, 420],
      "={{ JSON.stringify($json.refinementBody) }}"
    ),

    // ── 20. FORMAT REFINED OUTPUT ──
    makeCodeNode('format-refined', 'Format Refined Output', [3300, 420], formatRefinedCode),

    // ── 21. FORMAT DIRECT OUTPUT (false path) ──
    makeCodeNode('format-direct', 'Format Direct Output', [2820, 180], formatDirectCode),

    // ── 22. SEND TELEGRAM RESPONSE ──
    {
      parameters: {
        chatId: '={{ $json.chatId }}',
        text: '={{ $json.finalOutput }}',
        additionalFields: {
          parse_mode: 'Markdown'
        }
      },
      id: 'send-telegram',
      name: 'Send Telegram Response',
      type: 'n8n-nodes-base.telegram',
      typeVersion: 1.2,
      position: [3540, 300],
      credentials: {
        telegramApi: {
          id: 'telegram-bot',
          name: 'Telegram Bot'
        }
      }
    },

    // ── SENDING INDICATOR ──
    {
      parameters: {
        chatId: '={{ $json.message?.chat?.id || $json.chat_id }}',
        additionalFields: {},
        operation: 'sendChatAction',
        action: 'typing'
      },
      id: 'typing-indicator',
      name: 'Typing Indicator',
      type: 'n8n-nodes-base.telegram',
      typeVersion: 1.2,
      position: [140, 140],
      credentials: {
        telegramApi: {
          id: 'telegram-bot',
          name: 'Telegram Bot'
        }
      }
    }
  ],
  connections: {
    'Telegram Trigger': {
      main: [[
        { node: 'Preprocess & Build Prompts', type: 'main', index: 0 },
        { node: 'Typing Indicator', type: 'main', index: 0 }
      ]]
    },
    'Preprocess & Build Prompts': {
      main: [[
        { node: 'Novelty Agent (Opus 4)', type: 'main', index: 0 },
        { node: 'Specialized Agent (Gemini 2.5 Pro)', type: 'main', index: 0 },
        { node: 'MiniCAE Agent (Flash)', type: 'main', index: 0 },
        { node: 'IdeaCAE Agent (GPT-4.1)', type: 'main', index: 0 }
      ]]
    },
    'Novelty Agent (Opus 4)': {
      main: [[ { node: 'Merge Agent Outputs', type: 'main', index: 0 } ]]
    },
    'Specialized Agent (Gemini 2.5 Pro)': {
      main: [[ { node: 'Merge Agent Outputs', type: 'main', index: 1 } ]]
    },
    'MiniCAE Agent (Flash)': {
      main: [[ { node: 'Merge Agent Outputs', type: 'main', index: 2 } ]]
    },
    'IdeaCAE Agent (GPT-4.1)': {
      main: [[ { node: 'Merge Agent Outputs', type: 'main', index: 3 } ]]
    },
    'Merge Agent Outputs': {
      main: [[ { node: 'Build Synthesis Prompt', type: 'main', index: 0 } ]]
    },
    'Build Synthesis Prompt': {
      main: [[ { node: 'Synthesis (Opus 4)', type: 'main', index: 0 } ]]
    },
    'Synthesis (Opus 4)': {
      main: [[ { node: 'Build Critique Prompts', type: 'main', index: 0 } ]]
    },
    'Build Critique Prompts': {
      main: [[
        { node: 'Novelty Critique (Flash)', type: 'main', index: 0 },
        { node: 'Coherence Critique (Flash)', type: 'main', index: 0 },
        { node: 'Relevance Critique (Flash)', type: 'main', index: 0 },
        { node: 'Personalization Critique (Flash)', type: 'main', index: 0 }
      ]]
    },
    'Novelty Critique (Flash)': {
      main: [[ { node: 'Merge Critique Outputs', type: 'main', index: 0 } ]]
    },
    'Coherence Critique (Flash)': {
      main: [[ { node: 'Merge Critique Outputs', type: 'main', index: 1 } ]]
    },
    'Relevance Critique (Flash)': {
      main: [[ { node: 'Merge Critique Outputs', type: 'main', index: 2 } ]]
    },
    'Personalization Critique (Flash)': {
      main: [[ { node: 'Merge Critique Outputs', type: 'main', index: 3 } ]]
    },
    'Merge Critique Outputs': {
      main: [[ { node: 'Calculate Ensemble Score', type: 'main', index: 0 } ]]
    },
    'Calculate Ensemble Score': {
      main: [[ { node: 'Needs Refinement?', type: 'main', index: 0 } ]]
    },
    'Needs Refinement?': {
      main: [
        // True path (index 0) → Refinement
        [ { node: 'Build Refinement Prompt', type: 'main', index: 0 } ],
        // False path (index 1) → Direct output
        [ { node: 'Format Direct Output', type: 'main', index: 0 } ]
      ]
    },
    'Build Refinement Prompt': {
      main: [[ { node: 'Refinement (Opus 4)', type: 'main', index: 0 } ]]
    },
    'Refinement (Opus 4)': {
      main: [[ { node: 'Format Refined Output', type: 'main', index: 0 } ]]
    },
    'Format Refined Output': {
      main: [[ { node: 'Send Telegram Response', type: 'main', index: 0 } ]]
    },
    'Format Direct Output': {
      main: [[ { node: 'Send Telegram Response', type: 'main', index: 0 } ]]
    }
  },
  pinData: {},
  settings: {
    executionOrder: 'v1'
  },
  staticData: null,
  tags: [],
  triggerCount: 1,
  updatedAt: new Date().toISOString(),
  versionId: 'creativity-engine-v1'
};

// =============================================================================
// GENERATE OUTPUT
// =============================================================================
const outputPath = path.join(__dirname, '..', 'n8n-creativity-engine.json');
fs.writeFileSync(outputPath, JSON.stringify(workflow, null, 2));
console.log(`Generated: ${outputPath}`);
console.log(`Nodes: ${workflow.nodes.length}`);
console.log(`Connections: ${Object.keys(workflow.connections).length} source nodes`);
