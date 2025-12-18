# Creativity Engine

An advanced AI-powered creativity processing system with multi-agent architecture, memory systems, and iterative refinement.

## Architecture Overview

The Creativity Engine implements a sophisticated multi-layer architecture inspired by cognitive processes:

### Core Layers

1. **Entry Layer**: Request processing and preparation
2. **Memory Systems**: Semantic similarity, analogies, and activation-based recall
3. **Moment Layer**: Multi-agent creative processing
   - Novelty Agent: Generates novel and unexpected ideas
   - Specialized Agent: Domain-focused expertise
   - Mini-CAE Agent: Rapid creative analysis and enhancement
   - Idea-CAE Agent: Comprehensive idea development
4. **Critique Network**: Multi-agent evaluation
   - Novelty Critique Agent
   - Coherence Critique Agent
   - Relevance Critique Agent
   - Personalized Critique Agent
5. **Synthesis Orchestra**: Parallel output merging and refinement
6. **Iterative Refinement**: Self-improving quality loops
7. **Feedback & Learning**: RL-based continuous improvement

## Features

- **Multi-Agent Processing**: Parallel processing with specialized AI agents
- **Memory Systems**: Vector-based semantic memory with Pinecone
- **Critique Ensemble**: Multi-dimensional quality evaluation
- **Iterative Refinement**: Automatic quality improvement loops
- **Real-time Status**: WebSocket-based progress updates
- **Flexible Model Configuration**: Easy model switching via environment variables
- **Scalable Architecture**: Docker + Kubernetes ready

## Technology Stack

- **API Framework**: FastAPI
- **Database**: PostgreSQL with async SQLAlchemy
- **Vector Database**: Pinecone
- **Task Queue**: Celery + RabbitMQ
- **Cache**: Redis
- **AI Models**: OpenRouter (GPT-5.2, GPT-5 Nano)
- **Deployment**: Docker, Docker Compose, Kubernetes

## Quick Start

### Prerequisites

- Docker and Docker Compose
- OpenRouter API key
- Pinecone API key

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd creativity-engine
```

2. Create environment file:
```bash
cp .env.example .env
```

3. Configure your API keys in `.env`:
```env
OPENROUTER_API_KEY=your_openrouter_key_here
PINECONE_API_KEY=your_pinecone_key_here
PINECONE_ENVIRONMENT=your_pinecone_environment
```

4. Start the services:
```bash
docker-compose up -d
```

5. Access the API:
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- RabbitMQ Management: http://localhost:15672 (user: creativity, pass: creativity_password_change_me)

## API Usage

### Create a Creativity Request

**Simple Output (Fast):**
```bash
curl -X POST "http://localhost:8000/api/v1/requests" \
  -H "Content-Type: application/json" \
  -d '{
    "input_text": "Create a unique marketing campaign for sustainable coffee",
    "output_type": "simple"
  }'
```

**Full Processing (Comprehensive):**
```bash
curl -X POST "http://localhost:8000/api/v1/requests" \
  -H "Content-Type: application/json" \
  -d '{
    "input_text": "Create a unique marketing campaign for sustainable coffee",
    "output_type": "full",
    "metadata": {
      "preferences": {
        "style": "innovative",
        "tone": "professional"
      }
    }
  }'
```

**Creative Output with Controls:**
```bash
curl -X POST "http://localhost:8000/api/v1/requests" \
  -H "Content-Type: application/json" \
  -d '{
    "input_text": "Invent a new sport for low-gravity environments",
    "output_type": "full",
    "metadata": {
      "controls": {
        "randomness": 80,
        "speculation": 90,
        "ideas": 60
      }
    }
  }'
```

### Check Request Status

```bash
curl "http://localhost:8000/api/v1/requests/{request_id}"
```

### Get Detailed Processing Status

```bash
curl "http://localhost:8000/api/v1/status/{request_id}"
```

### WebSocket Real-time Updates

```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/ws/status/{request_id}');

ws.onmessage = (event) => {
  const update = JSON.parse(event.data);
  console.log('Status update:', update);
};
```

### Submit Feedback

```bash
curl -X POST "http://localhost:8000/api/v1/feedback" \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "your-request-id",
    "novelty_score": 0.9,
    "coherence_score": 0.85,
    "relevance_score": 0.95,
    "overall_rating": 5,
    "feedback_text": "Excellent output!"
  }'
```

## Configuration

### Model Configuration

The system uses two model tiers configurable via environment variables:

- `MAIN_MODEL`: Primary model for complex creative tasks (default: openai/gpt-5.2)
- `FAST_MODEL`: Lightweight model for quick tasks (default: openai/gpt-5-nano)

Change models by updating `.env`:
```env
MAIN_MODEL=openai/gpt-5.2
FAST_MODEL=openai/gpt-5-nano
MODEL_TEMPERATURE=0.7
MODEL_MAX_TOKENS=4096
```

### Processing Configuration

```env
MAX_CONCURRENT_TASKS=10
TASK_TIMEOUT=600
ENABLE_SIMPLE_OUTPUT=true
ENABLE_ITERATIVE_REFINEMENT=true
MAX_REFINEMENT_ITERATIONS=3
```

### Memory Configuration

```env
MEMORY_ACTIVATION_THRESHOLD=0.7
MEMORY_DECAY_RATE=0.95
SEMANTIC_SIMILARITY_THRESHOLD=0.75
```

### Critique Configuration

```env
CRITIQUE_ENSEMBLE_THRESHOLD=0.6
```

## Architecture Deep Dive

### Processing Pipeline

```
Input → Preparation → Memory Retrieval → Moment Agents (parallel) →
Synthesis → Critique → Refinement (if needed) → Output
```

### Moment Layer Agents

1. **Novelty Agent** (temperature: 0.9)
   - Generates highly novel and unexpected ideas
   - Breaks patterns and challenges assumptions
   - Explores metaphorical spaces

2. **Specialized Agent** (temperature: 0.7)
   - Domain-specific expertise
   - Applies field-specific techniques
   - References relevant precedents

3. **Mini-CAE Agent** (temperature: 0.6)
   - Rapid creative analysis
   - Identifies strengths and opportunities
   - Suggests focused enhancements

4. **Idea-CAE Agent** (temperature: 0.75)
   - Comprehensive idea development
   - Multi-dimensional exploration
   - Implementation pathways

### Critique Network

All critique agents run in parallel and provide scores (0.0-1.0):

- **Novelty**: Originality and uniqueness
- **Coherence**: Logical consistency and flow
- **Relevance**: Alignment with input and goals
- **Personalization**: User preference matching

Scores are combined using weighted ensemble (configurable weights).

### Memory System

- **Storage**: PostgreSQL + Pinecone vector database
- **Types**: Monograph, Audio, Prototype, Semantic, Episodic, Working
- **Retrieval**: Semantic similarity search with activation weights
- **Management**: Automatic decay and activation tracking

### Iterative Refinement

If ensemble score < threshold (default: 0.6):
1. Critique identifies weaknesses
2. System generates refined version
3. Re-evaluate with critique
4. Repeat up to max iterations (default: 3)

## Development

### Project Structure

```
creativity-engine/
├── src/
│   ├── agents/           # AI agents
│   │   ├── moment/       # Moment layer agents
│   │   └── critique/     # Critique network agents
│   ├── api/              # FastAPI routes
│   ├── database/         # Database session management
│   ├── models/           # SQLAlchemy models
│   ├── memory/           # Memory systems
│   ├── processing/       # Task queue and pipeline
│   ├── synthesis/        # Synthesis orchestra
│   ├── utils/            # Utilities (logging, clients)
│   ├── config.py         # Configuration
│   └── main.py           # FastAPI app
├── docker-compose.yml    # Development environment
├── Dockerfile            # Container definition
├── requirements.txt      # Python dependencies
└── README.md             # This file
```

### Running Tests

```bash
# Install development dependencies
pip install -r requirements.txt

# Run tests
pytest

# Run with coverage
pytest --cov=src tests/
```

### Code Quality

```bash
# Format code
black src/

# Lint
ruff check src/

# Type checking
mypy src/
```

## Production Deployment

### Kubernetes

Kubernetes manifests are provided for production deployment:

```bash
# Apply configurations
kubectl apply -f k8s/

# Check status
kubectl get pods -n creativity-engine
```

### Environment Variables

Ensure all required environment variables are set:
- `OPENROUTER_API_KEY`
- `PINECONE_API_KEY`
- `PINECONE_ENVIRONMENT`
- `POSTGRES_PASSWORD`
- `RABBITMQ_PASSWORD`
- Database connection details

### Scaling

Scale workers horizontally:
```bash
# Docker Compose
docker-compose up -d --scale worker=4

# Kubernetes
kubectl scale deployment creativity-worker --replicas=4
```

## Monitoring

### Health Checks

- Basic health: `GET /health`
- Readiness: `GET /health/ready`
- Liveness: `GET /health/live`

### Metrics

Prometheus metrics available at `/metrics` when `ENABLE_METRICS=true`

### Logging

Structured JSON logging with configurable levels:
```env
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

## API Reference

Full API documentation available at `/docs` (Swagger UI) and `/redoc` (ReDoc).

### Main Endpoints

- `POST /api/v1/requests` - Create creativity request
- `GET /api/v1/requests/{id}` - Get request details
- `GET /api/v1/requests` - List requests (with filters)
- `DELETE /api/v1/requests/{id}` - Cancel request
- `GET /api/v1/status/{id}` - Get detailed status
- `WS /api/v1/ws/status/{id}` - WebSocket status stream
- `POST /api/v1/feedback` - Submit feedback
- `GET /api/v1/feedback/{request_id}` - Get feedback

## Troubleshooting

### Common Issues

**Database connection error:**
- Ensure PostgreSQL is running
- Check connection credentials in `.env`
- Verify network connectivity

**Pinecone initialization error:**
- Verify API key and environment
- Check Pinecone dashboard for service status
- Ensure index exists or can be created

**Worker not processing tasks:**
- Check RabbitMQ is running
- Verify worker logs: `docker-compose logs worker`
- Ensure queue is not full

**Slow processing:**
- Increase concurrent tasks: `MAX_CONCURRENT_TASKS`
- Scale workers: `docker-compose up -d --scale worker=4`
- Consider using `output_type: simple` for faster results

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

[Your License Here]

## Support

For issues and questions:
- GitHub Issues: [repository-url]/issues
- Documentation: [documentation-url]

## Roadmap

- [ ] Enhanced RL training pipeline
- [ ] Additional memory types (Visual, Auditory)
- [ ] Multi-modal input support
- [ ] Advanced analogy generation
- [ ] Performance optimizations
- [ ] Extended agent library
- [ ] Fine-tuning capabilities
- [ ] A/B testing framework

## Acknowledgments

Built with advanced AI architecture inspired by cognitive science and creative processes.
