import os
import json
import requests
import streamlit as st
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dotenv import load_dotenv

from agno.agent.agent import Agent
from agno.run.response import RunEvent, RunResponse
from agno.storage.postgres import PostgresStorage
from agno.utils.log import logger
from agno.workflow.workflow import Workflow
from pydantic import BaseModel, Field

# Load environment variables
load_dotenv()


class Release(BaseModel):
    project_name: str = Field(..., description="Name of the project")
    version: str = Field(..., description="Release version")
    description: str = Field(..., description="Release notes summary")
    date: str = Field(..., description="Release date")


class IssuePattern(BaseModel):
    pattern: str = Field(..., description="Issue pattern or category")
    count: int = Field(..., description="Number of occurrences")


class CompetitorAnalysis(BaseModel):
    project_name: str = Field(..., description="Name of the competitor project")
    recent_releases: List[Release] = Field(..., description="Recent releases")
    key_features: List[str] = Field(..., description="Key new features")
    recurring_issues: List[IssuePattern] = Field(..., description="Common issue patterns")


class WeeklyReport(BaseModel):
    report_date: str = Field(..., description="Report date")
    analyses: List[CompetitorAnalysis] = Field(..., description="Competitor analyses")
    industry_trends: List[str] = Field(..., description="Cross-competitor trends")
    recommendations: List[str] = Field(..., description="Strategic recommendations")


class CompetitiveAnalysesList(BaseModel):
    analyses: List[CompetitorAnalysis] = Field(..., description="List of competitor analyses")


class CompetitiveIntelligenceWorkflow(Workflow):
    description: str = "Analyze competitor GitHub repositories and generate weekly intelligence reports using agno agents."

    data_analyzer: Agent = Agent(
        name="Data Analyzer",
        instructions=[
            "You are a competitive intelligence data analyst.",
            "Analyze GitHub data for a competitor project including releases and issues.",
            "Extract key features from releases, identify recurring issue patterns, and categorize problems.",
            "Focus on actionable insights for product managers.",
            "Return structured analysis with recent releases, key features, and issue patterns.",
            "Be concise and focus on the most important insights."
        ],
        response_model=CompetitorAnalysis,
    )

    report_generator: Agent = Agent(
        name="Report Generator", 
        instructions=[
            "You are a strategic intelligence analyst for product managers.",
            "Generate comprehensive weekly competitive intelligence reports.",
            "Analyze multiple competitor insights to identify industry trends and strategic opportunities.",
            "Provide actionable recommendations based on competitive analysis.",
            "Focus on market positioning, feature gaps, and strategic advantages.",
            "Be concise and focus on the most important strategic insights."
        ],
        response_model=WeeklyReport,
    )

    def get_github_data(self, owner: str, repo: str) -> Dict:
        """Fetch GitHub data using API with reduced data size for AI processing"""
        token = os.getenv("GITHUB_TOKEN")
        headers = {"Authorization": f"token {token}"} if token else {}
        
        releases_url = f"https://api.github.com/repos/{owner}/{repo}/releases"
        issues_url = f"https://api.github.com/repos/{owner}/{repo}/issues"
        
        try:
            # Get recent releases (limit to 3 for token efficiency)
            releases_response = requests.get(releases_url, headers=headers)
            releases_data = releases_response.json() if releases_response.status_code == 200 else []
            
            # Limit release data to essential fields only
            limited_releases = []
            for release in releases_data[:3]:  # Only last 3 releases
                limited_releases.append({
                    "tag_name": release.get("tag_name", ""),
                    "name": release.get("name", ""),
                    "body": release.get("body", "")[:500],  # Limit to 500 chars
                    "published_at": release.get("published_at", "")
                })
            
            # Get recent issues (reduce to 20 for token efficiency)
            cutoff_date = (datetime.now() - timedelta(days=7)).isoformat()
            issues_params = {"since": cutoff_date, "state": "all", "per_page": 20}  # Reduced from 50
            issues_response = requests.get(issues_url, headers=headers, params=issues_params)
            issues_data = issues_response.json() if issues_response.status_code == 200 else []
            
            # Limit issue data to essential fields only
            limited_issues = []
            for issue in issues_data[:20]:  # Only first 20 issues
                limited_issues.append({
                    "title": issue.get("title", ""),
                    "body": (issue.get("body", "") or "")[:200],  # Limit to 200 chars
                    "labels": [label.get("name", "") for label in issue.get("labels", [])][:3],  # Max 3 labels
                    "state": issue.get("state", ""),
                    "created_at": issue.get("created_at", "")
                })
            
            return {
                "releases": limited_releases,
                "issues": limited_issues
            }
        except Exception as e:
            logger.error(f"Error fetching data for {owner}/{repo}: {e}")
            return {"releases": [], "issues": []}

    def analyze_competitor(self, project_name: str, owner: str, repo: str) -> Optional[CompetitorAnalysis]:
        """Analyze a single competitor using agno data analyzer agent"""
        github_data = self.get_github_data(owner, repo)
        
        analysis_prompt = f"""
        Analyze competitive intelligence for {project_name} ({owner}/{repo}):
        
        Recent Releases: {json.dumps(github_data["releases"])}
        Recent Issues: {json.dumps(github_data["issues"])}
        
        Provide structured analysis focusing on:
        1. Key new features from releases
        2. Common issue patterns
        3. Strategic insights for product managers
        """
        
        try:
            response: RunResponse = self.data_analyzer.run(analysis_prompt)
            if response and response.content and isinstance(response.content, CompetitorAnalysis):
                return response.content
            else:
                logger.warning(f"Invalid response from data analyzer for {project_name}")
                return None
        except Exception as e:
            logger.error(f"Error analyzing {project_name}: {e}")
            return None

    def generate_weekly_report(self, analyses: List[CompetitorAnalysis]) -> Optional[WeeklyReport]:
        """Generate weekly intelligence report using agno report generator agent"""
        report_prompt = f"""
        Generate competitive intelligence report from competitor analyses:
        
        Data: {json.dumps([analysis.model_dump() for analysis in analyses])}
        
        Provide:
        1. Industry trends across competitors
        2. Strategic recommendations for product management
        3. Competitive threats and opportunities
        """
        
        try:
            response: RunResponse = self.report_generator.run(report_prompt)
            if response and response.content and isinstance(response.content, WeeklyReport):
                return response.content
            else:
                logger.warning("Invalid response from report generator")
                return None
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return None

    def get_cached_report(self, week_key: str) -> Optional[WeeklyReport]:
        """Get cached report from session state"""
        if "reports" in self.session_state:
            for cached_report in self.session_state["reports"]:
                if cached_report["week"] == week_key:
                    return WeeklyReport.model_validate(cached_report["data"])
        return None

    def run(self, selected_competitors: Dict, use_cache: bool = False) -> RunResponse:
        """Main workflow execution using agno framework"""
        logger.info("Starting agno competitive intelligence analysis...")
        current_week = datetime.now().strftime("%Y-W%U")
        
        if use_cache:
            cached_report = self.get_cached_report(current_week)
            if cached_report:
                return RunResponse(
                    run_id=self.run_id,
                    content=cached_report,
                )

        # Analyze each competitor using agno agents
        analyses = []
        for project_name, config in selected_competitors.items():
            logger.info(f"Analyzing {project_name} with agno agents...")
            analysis = self.analyze_competitor(project_name, config["owner"], config["repo"])
            if analysis:
                analyses.append(analysis)

        if not analyses:
            return RunResponse(
                run_id=self.run_id,
                content="No competitor data could be analyzed.",
            )

        # Generate weekly report using agno agent
        weekly_report = self.generate_weekly_report(analyses)
        if not weekly_report:
            return RunResponse(
                run_id=self.run_id,
                content="Failed to generate weekly report.",
            )

        # Cache report
        if "reports" not in self.session_state:
            self.session_state["reports"] = []
        self.session_state["reports"].append({
            "week": current_week,
            "data": weekly_report.model_dump()
        })

        return RunResponse(
            run_id=self.run_id,
            content=weekly_report,
        )


def display_agno_streamlit_dashboard():
    """Streamlit dashboard using agno competitive intelligence workflow"""
    st.set_page_config(
        page_title="🤖 Agno Competitive Intelligence",
        page_icon="🤖",
        layout="wide"
    )
    
    st.title("🤖 Agno Competitive Intelligence Dashboard")
    st.markdown("*Powered by agno AI agents for strategic analysis*")
    st.markdown("---")
    
    # Display agno framework info
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        st.info("🤖 **Data Analyzer Agent**\nAnalyzes GitHub data")
    with col2:
        st.info("📊 **Report Generator Agent**\nCreates strategic insights")  
    with col3:
        st.info("🔄 **Workflow Management**\nOrchestrates analysis")
    
    # Check GitHub token
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        st.error("❌ GitHub token not found! Please set GITHUB_TOKEN in your .env file")
        return
    
    # Initialize workflow
    try:
        # Try with PostgreSQL storage first, fallback to basic storage
        try:
            workflow = CompetitiveIntelligenceWorkflow(
                session_id="competitive-intelligence-agno",
                storage=PostgresStorage(
                    table_name="competitive_intelligence_workflows",
                    db_url="postgresql+psycopg://ai:ai@localhost:5532/ai",
                ),
            )
            st.sidebar.success("✅ PostgreSQL storage connected")
        except Exception as e:
            # Fallback to basic workflow without postgres
            workflow = CompetitiveIntelligenceWorkflow(
                session_id="competitive-intelligence-agno"
            )
            st.sidebar.warning("⚠️ Using basic storage (no PostgreSQL)")
            
    except Exception as e:
        st.error(f"Failed to initialize agno workflow: {e}")
        return
    
    # Sidebar controls
    st.sidebar.title("⚙️ Agno Controls")
    
    # Competitor selection
    st.sidebar.subheader("Select Competitors")
    
    competitors = {
        "Next.js": {"owner": "vercel", "repo": "next.js"},
        "Nuxt": {"owner": "nuxt", "repo": "nuxt"},
        "SvelteKit": {"owner": "sveltejs", "repo": "kit"},
        "Remix": {"owner": "remix-run", "repo": "remix"},
        "Astro": {"owner": "withastro", "repo": "astro"}
    }
    
    selected_competitors = {}
    for name, config in competitors.items():
        if st.sidebar.checkbox(name, value=True):
            selected_competitors[name] = config
    
    use_cache = st.sidebar.checkbox("Use Cached Data", value=False)
    
    # Analysis button
    if st.sidebar.button("🤖 Run Agno Analysis", type="primary"):
        if not selected_competitors:
            st.error("Please select at least one competitor")
        else:
            with st.spinner("🤖 Agno agents analyzing competitors..."):
                # Run agno workflow following product manager pattern
                response: RunResponse = workflow.run(
                    selected_competitors=selected_competitors,
                    use_cache=use_cache
                )
                
                if response and response.content and isinstance(response.content, WeeklyReport):
                    st.session_state.agno_report = response.content
                    st.success(f"✅ Agno analysis complete! {len(response.content.analyses)} competitors analyzed.")
                else:
                    st.error("❌ Agno analysis failed")
    
    # Display report
    if 'agno_report' in st.session_state:
        report = st.session_state.agno_report
        
        # Report header
        st.header(f"📊 Agno Intelligence Report - {report.report_date}")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            st.metric("Competitors Analyzed", len(report.analyses))
        with col2:
            st.metric("AI Agents Used", "2")
        
        # Competitor Analysis Section
        st.subheader("🏢 Competitor Analysis (by Agno Agents)")
        
        if report.analyses:
            # Create tabs for each competitor
            competitor_names = [analysis.project_name for analysis in report.analyses]
            competitor_tabs = st.tabs(competitor_names)
            
            for tab, analysis in zip(competitor_tabs, report.analyses):
                with tab:
                    st.markdown(f"*Analysis by agno Data Analyzer Agent*")
                    
                    col1, col2 = st.columns([1, 1])
                    
                    with col1:
                        st.markdown("### 🚀 Recent Releases")
                        if analysis.recent_releases:
                            for release in analysis.recent_releases:
                                with st.expander(f"{release.version} - {release.date}"):
                                    st.write(release.description)
                        else:
                            st.info("No recent releases")
                        
                        st.markdown("### ⭐ Key Features")
                        for feature in analysis.key_features:
                            st.markdown(f"• {feature}")
                    
                    with col2:
                        st.markdown("### 🐛 Recurring Issues")
                        if analysis.recurring_issues:
                            for issue in analysis.recurring_issues:
                                st.metric(label=issue.pattern, value=f"{issue.count} occurrences")
                        else:
                            st.info("No significant patterns found")
        
        # Strategic Insights Section
        st.markdown("---")
        st.subheader("🧠 Strategic Insights (by Agno Report Generator)")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("### 📈 Industry Trends")
            for trend in report.industry_trends:
                st.markdown(f"• {trend}")
        
        with col2:
            st.markdown("### 💡 Strategic Recommendations")
            for rec in report.recommendations:
                st.markdown(f"• {rec}")
    
    else:
        st.info("👆 Click 'Run Agno Analysis' to generate intelligence using AI agents!")
        
        st.markdown("## 🤖 Agno Framework Features")
        st.markdown("""
        - **🧠 AI Agents**: Specialized agents for data analysis and report generation
        - **📋 Structured Models**: Pydantic models for consistent data handling  
        - **🔄 Workflow Management**: Robust workflow orchestration with retry logic
        - **💾 PostgreSQL Storage**: Optional persistent storage for caching
        - **📊 Real-time Analysis**: Live GitHub API integration
        - **🎯 Strategic Focus**: Product manager-focused insights and recommendations
        """)


# Create the agno workflow instance
competitive_intelligence = CompetitiveIntelligenceWorkflow(
    session_id="competitive-intelligence-agno"
)

# Run Streamlit app
if __name__ == "__main__":
    display_agno_streamlit_dashboard()
