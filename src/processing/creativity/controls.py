from typing import Dict, Any

def slider_to_band(value: int, min_band: int = 1, max_band: int = 10) -> int:
    """Map a 0-100 slider value to a discrete band."""
    # Clamp value
    v = max(0, min(100, value))
    # Normalize to 0-1
    norm = v / 100.0
    # Map to band
    span = max_band - min_band
    return int(min_band + (span * norm))

def randomness_to_temperature(band: int, base: float = 0.5, spread: float = 0.5) -> float:
    """Map 1-10 band to temperature."""
    # band is 1-10
    norm = (band - 1) / 9.0
    return base + (spread * norm)

def map_sliders_to_params(
    randomness: int,
    speculation: int,
    ideas: int
) -> Dict[str, Dict[str, Any]]:
    """
    Map raw slider values (0-100) to kernel parameters.
    Returns:
        {
            "sampling": {temperature, top_p, ...},
            "kernel": {what_if_branches, future_layers, idea_count, ...}
        }
    """
    
    # 1. Randomness -> Sampling
    rand_band = slider_to_band(randomness, 1, 10)
    # Base temp 0.6, spread up to 1.1?
    temp = randomness_to_temperature(rand_band, base=0.6, spread=0.6)
    temp = min(1.2, max(0.1, temp))
    
    top_p = 0.85 + (0.14 * (randomness / 100.0))
    top_p = min(0.99, top_p)
    
    presence_penalty = 0.0 + (0.5 * (randomness / 100.0))
    frequency_penalty = 0.0 + (0.5 * (randomness / 100.0))

    sampling = {
        "temperature": temp,
        "top_p": top_p,
        "presence_penalty": presence_penalty,
        "frequency_penalty": frequency_penalty,
    }

    # 2. Speculation -> Branches/Layers
    # Speculation 0-100
    spec_band = slider_to_band(speculation, 1, 10)
    
    # Low speculation: 1 branch, 1 layer
    # High speculation: 3-5 branches, 2-3 layers
    what_if_branches = 1
    future_layers = 1
    
    if spec_band > 3:
        what_if_branches = 2
    if spec_band > 6:
        what_if_branches = 3
        future_layers = 2
    if spec_band > 8:
        what_if_branches = 4
        future_layers = 2
        
    # 3. Ideas -> Count/Density
    idea_band = slider_to_band(ideas, 3, 15)
    idea_count = idea_band
    
    # Converge bias: High ideas -> lower converge bias (more divergent)
    # Low ideas -> higher convert bias (more focused)
    converge_bias = 1.0 - (ideas / 100.0)
    
    # Serendipity seeds: related to Randomness + Speculation
    # More randomness -> more seeds
    seeds_count = slider_to_band((randomness + speculation) // 2, 0, 8)
    
    # Graph hops
    graph_hop_distance = 1
    if speculation > 50:
        graph_hop_distance = 2
    if speculation > 80:
        graph_hop_distance = 3

    kernel = {
        "what_if_branches": what_if_branches,
        "future_layers": future_layers,
        "idea_count": idea_count,
        "converge_bias": converge_bias,
        "serendipity_cross_domain_seeds": seeds_count,
        "graph_hop_distance": graph_hop_distance,
    }

    return {
        "sampling": sampling,
        "kernel": kernel,
    }
