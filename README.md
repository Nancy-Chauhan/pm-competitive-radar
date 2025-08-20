# AI Competitive Intelligence Agent

🤖 **AI-powered competitive intelligence using the agno framework**

Automatically analyzes competitor GitHub repositories and generates strategic insights using AI agents.

## Features

- 🔍 **Real-time Analysis** - Live GitHub data from 5 major competitors
- 🤖 **AI Agents** - Data analyzer and report generator using OpenAI
- 📊 **Interactive Dashboard** - Streamlit interface with professional UI
- 🏢 **5 Competitors** - Next.js, Nuxt, SvelteKit, Remix, Astro
- 📈 **Strategic Insights** - Industry trends and recommendations
- 💾 **Persistent Storage** - PostgreSQL for caching results

## Quick Start

1. **Clone the repository**
```bash
git clone <your-repo-url>
cd competitive-intelligence-agent
```

2. **Create virtual environment**
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set environment variables**
```bash
export GITHUB_TOKEN="your_github_token"
export OPENAI_API_KEY="your_openai_api_key"
```

5. **Run the app**
```bash
streamlit run agno_app.py
```

6. **Open dashboard**
- Go to http://localhost:8501
- Select competitors to analyze
- Click "Run Agno Analysis"

## Environment Variables

Create a `.env` file:
```
GITHUB_TOKEN=your_github_token_here
OPENAI_API_KEY=your_openai_api_key_here
```

## Get API Keys

- **GitHub Token**: https://github.com/settings/tokens
- **OpenAI API Key**: https://platform.openai.com/account/api-keys

## Files

- `agno_app.py` - Main application with agno framework
- `real_data_app.py` - Simplified version without agno
- `demo_app.py` - Demo with mock data

## Requirements

- Python 3.8+
- GitHub API token
- OpenAI API key
- Optional: PostgreSQL for storage

## Technologies

- **agno** - AI agent framework
- **Streamlit** - Web interface
- **OpenAI** - AI analysis
- **GitHub API** - Competitor data
- **PostgreSQL** - Data storage

## License

MIT License
