import os
import json
import requests
import streamlit as st
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from agno.agent.agent import Agent
from agno.run.response import RunEvent, RunResponse
from agno.storage.postgres import PostgresStorage
from agno.utils.log import logger
from agno.workflow.workflow import Workflow
from pydantic import BaseModel, Field


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


class CompetitiveIntelligenceWorkflow(Workflow):
    description: str = "Analyze competitor GitHub repositories and generate weekly intelligence reports."

    data_analyzer: Agent = Agent(
        name="Data Analyzer",
        instructions=[
            "Analyze GitHub data for a competitor project including releases and issues.",
            "Extract key features from releases and identify recurring issue patterns.",
            "Summarize the data in a structured format."
        ],
        response_model=CompetitorAnalysis,
    )

    report_generator: Agent = Agent(
        name="Report Generator", 
        instructions=[
            "Generate a comprehensive weekly competitive intelligence report.",
            "Identify industry trends and provide strategic recommendations.",
            "Focus on actionable insights for product managers."
        ],
        response_model=WeeklyReport,
    )

    def get_github_data(self, owner: str, repo: str) -> Dict:
        token = os.getenv("GITHUB_TOKEN")
        headers = {"Authorization": f"token {token}"} if token else {}
        
        releases_url = f"https://api.github.com/repos/{owner}/{repo}/releases"
        issues_url = f"https://api.github.com/repos/{owner}/{repo}/issues"
        
        try:
            # Get recent releases
            releases_response = requests.get(releases_url, headers=headers)
            releases_data = releases_response.json() if releases_response.status_code == 200 else []
            
            # Get recent issues
            cutoff_date = (datetime.now() - timedelta(days=7)).isoformat()
            issues_params = {"since": cutoff_date, "state": "all", "per_page": 50}
            issues_response = requests.get(issues_url, headers=headers, params=issues_params)
            issues_data = issues_response.json() if issues_response.status_code == 200 else []
            
            return {
                "releases": releases_data[:5],  # Last 5 releases
                "issues": issues_data
            }
        except Exception as e:
            logger.error(f"Error fetching data for {owner}/{repo}: {e}")
            return {"releases": [], "issues": []}

    def analyze_competitor(self, project_name: str, owner: str, repo: str) -> Optional[CompetitorAnalysis]:
        github_data = self.get_github_data(owner, repo)
        
        analysis_prompt = f"""
        Analyze competitor: {project_name}
        GitHub data: {json.dumps(github_data)}
        
        Extract key insights about recent releases and common issues.
        """
        
        try:
            response: RunResponse = self.data_analyzer.run(analysis_prompt)
            if response and response.content and isinstance(response.content, CompetitorAnalysis):
                return response.content
            else:
                logger.warning(f"Invalid response for {project_name}")
                return None
        except Exception as e:
            logger.error(f"Error analyzing {project_name}: {e}")
            return None

    def generate_weekly_report(self, analyses: List[CompetitorAnalysis]) -> Optional[WeeklyReport]:
        report_prompt = f"""
        Generate weekly competitive intelligence report.
        Competitor analyses: {json.dumps([a.model_dump() for a in analyses])}
        
        Identify trends and provide strategic recommendations.
        """
        
        try:
            response: RunResponse = self.report_generator.run(report_prompt)
            if response and response.content and isinstance(response.content, WeeklyReport):
                return response.content
            else:
                logger.warning("Invalid report response")
                return None
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return None

    def get_cached_report(self, week_key: str) -> Optional[WeeklyReport]:
        if "reports" in self.session_state:
            for cached_report in self.session_state["reports"]:
                if cached_report["week"] == week_key:
                    return WeeklyReport.model_validate(cached_report["data"])
        return None

    def run(self, use_cache: bool = False) -> Optional[WeeklyReport]:
        logger.info("Starting competitive intelligence analysis...")
        current_week = datetime.now().strftime("%Y-W%U")
        
        if use_cache:
            cached_report = self.get_cached_report(current_week)
            if cached_report:
                return cached_report

        # Competitor projects to analyze
        competitors = {
            "Next.js": {"owner": "vercel", "repo": "next.js"},
            "Nuxt": {"owner": "nuxt", "repo": "nuxt"},
            "SvelteKit": {"owner": "sveltejs", "repo": "kit"},
            "Remix": {"owner": "remix-run", "repo": "remix"},
            "Astro": {"owner": "withastro", "repo": "astro"}
        }

        # Analyze each competitor
        analyses = []
        for project_name, config in competitors.items():
            logger.info(f"Analyzing {project_name}...")
            analysis = self.analyze_competitor(project_name, config["owner"], config["repo"])
            if analysis:
                analyses.append(analysis)

        if not analyses:
            logger.error("No competitor data could be analyzed.")
            return None

        # Generate weekly report
        weekly_report = self.generate_weekly_report(analyses)
        if not weekly_report:
            logger.error("Failed to generate weekly report.")
            return None

        # Cache report
        if "reports" not in self.session_state:
            self.session_state["reports"] = []
        self.session_state["reports"].append({
            "week": current_week,
            "data": weekly_report.model_dump()
        })

        return weekly_report


def display_streamlit_dashboard():
    """Streamlit dashboard for competitive intelligence"""
    st.set_page_config(
        page_title="🔍 Competitive Intelligence Dashboard",
        page_icon="🔍",
        layout="wide"
    )
    
    st.title("🔍 Competitive Intelligence Dashboard")
    st.markdown("---")
    
    # Sidebar controls
    st.sidebar.title("Controls")
    
    if st.sidebar.button("🔄 Generate New Report", type="primary"):
        with st.spinner("Analyzing competitors..."):
            # Initialize workflow
            workflow = CompetitiveIntelligenceWorkflow(
                session_id="competitive-intelligence",
                storage=PostgresStorage(
                    table_name="competitive_intelligence_workflows",
                    db_url="postgresql+psycopg://ai:ai@localhost:5532/ai",
                ),
            )
            
            # Run analysis
            report = workflow.run(use_cache=False)
            if report:
                st.session_state.current_report = report
                st.success("✅ Report generated successfully!")
            else:
                st.error("❌ Failed to generate report")
    
    use_cache = st.sidebar.checkbox("Use Cached Data", value=True)
    
    # Load or generate report
    if 'current_report' not in st.session_state:
        with st.spinner("Loading competitive intelligence data..."):
            workflow = CompetitiveIntelligenceWorkflow(
                session_id="competitive-intelligence",
                storage=PostgresStorage(
                    table_name="competitive_intelligence_workflows",
                    db_url="postgresql+psycopg://ai:ai@localhost:5532/ai",
                ),
            )
            report = workflow.run(use_cache=use_cache)
            if report:
                st.session_state.current_report = report
    
    # Display report if available
    if 'current_report' in st.session_state:
        report = st.session_state.current_report
        
        # Report header
        col1, col2 = st.columns([3, 1])
        with col1:
            st.header(f"📊 Weekly Report - {report.report_date}")
        with col2:
            st.metric("Competitors Analyzed", len(report.analyses))
        
        # Competitor Analysis Section
        st.subheader("🏢 Competitor Analysis")
        
        # Create tabs for each competitor
        competitor_tabs = st.tabs([analysis.project_name for analysis in report.analyses])
        
        for tab, analysis in zip(competitor_tabs, report.analyses):
            with tab:
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
                            st.metric(issue.pattern, issue.count, label="occurrences")
                    else:
                        st.info("No significant patterns found")
        
        # Industry Trends Section
        st.markdown("---")
        st.subheader("📈 Industry Trends")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("### 🎯 Key Trends")
            for trend in report.industry_trends:
                st.markdown(f"• {trend}")
        
        with col2:
            st.markdown("### 💡 Recommendations")
            for rec in report.recommendations:
                st.markdown(f"• {rec}")
    
    else:
        st.warning("⚠️ No report data available. Click 'Generate New Report' to start analysis.")
        st.info("Make sure your GitHub token is configured: `export GITHUB_TOKEN=your_token`")


# Create the workflow
competitive_intelligence = CompetitiveIntelligenceWorkflow(
    session_id="competitive-intelligence",
    storage=PostgresStorage(
        table_name="competitive_intelligence_workflows",
        db_url="postgresql+psycopg://ai:ai@localhost:5532/ai",
    ),
)

# Run Streamlit app
if __name__ == "__main__":
    display_streamlit_dashboard()
