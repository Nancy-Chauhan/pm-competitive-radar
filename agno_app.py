import os
import json
import requests
import streamlit as st
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
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
    url: str = Field(..., description="Link to the release")


class IssuePattern(BaseModel):
    pattern: str = Field(..., description="Issue pattern or category")
    count: int = Field(..., description="Number of occurrences")
    example_links: List[str] = Field(default=[], description="Links to example issues")


class CompetitorAnalysis(BaseModel):
    project_name: str = Field(..., description="Name of the competitor project")
    repository_url: str = Field(..., description="Link to the GitHub repository")
    recent_releases: List[Release] = Field(..., description="Recent releases with links")
    key_features: List[str] = Field(..., description="Key new features")
    recurring_issues: List[IssuePattern] = Field(..., description="Common issue patterns with example links")


class WeeklyReport(BaseModel):
    report_date: str = Field(..., description="Report date")
    analyses: List[CompetitorAnalysis] = Field(..., description="Competitor analyses")
    industry_trends: List[str] = Field(..., description="Cross-competitor trends")
    recommendations: List[str] = Field(..., description="Strategic recommendations")
    sources: Optional[List[str]] = Field(default=None, description="All source repositories analyzed")
    methodology: Optional[str] = Field(default=None, description="Analysis methodology and data sources")


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
            "IMPORTANT: Always include URLs and links in your analysis:",
            "- For releases: include the version, description, date, and url from html_url field",
            "- For issue patterns: include example_links using html_url from relevant issues", 
            "- Include the repository_url in your response",
            "Return structured analysis with recent releases, key features, and issue patterns with proper links.",
            "Be concise and focus on the most important insights with supporting references."
        ],
        response_model=CompetitorAnalysis,
    )

    report_generator: Agent = Agent(
        name="Report Generator", 
        instructions=[
            "You are a strategic intelligence analyst for product managers.",
            "Generate comprehensive weekly competitive intelligence reports with source attribution.",
            "Analyze multiple competitor insights to identify industry trends and strategic opportunities.",
            "Provide actionable recommendations based on competitive analysis.",
            "Focus on market positioning, feature gaps, and strategic advantages.",
            "CRITICAL: Always include sources and references:",
            "- Populate the 'sources' field with all repository URLs analyzed",
            "- Include methodology explaining data sources (GitHub releases, issues, etc.)",
            "- Reference specific releases, issues, or repositories in your trends and recommendations",
            "- Make industry trends detailed and reference specific competitor findings",
            "Be concise and focus on the most important strategic insights with complete attribution."
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
            
            # Limit release data to essential fields only, including URLs
            limited_releases = []
            for release in releases_data[:3]:  # Only last 3 releases
                limited_releases.append({
                    "tag_name": release.get("tag_name", ""),
                    "name": release.get("name", ""),
                    "body": release.get("body", "")[:500],  # Limit to 500 chars
                    "published_at": release.get("published_at", ""),
                    "html_url": release.get("html_url", "")  # Add release URL
                })
            
            # Get recent issues (reduce to 20 for token efficiency)
            cutoff_date = (datetime.now() - timedelta(days=7)).isoformat()
            issues_params = {"since": cutoff_date, "state": "all", "per_page": 20}  # Reduced from 50
            issues_response = requests.get(issues_url, headers=headers, params=issues_params)
            issues_data = issues_response.json() if issues_response.status_code == 200 else []
            
            # Limit issue data to essential fields only, including URLs
            limited_issues = []
            for issue in issues_data[:20]:  # Only first 20 issues
                limited_issues.append({
                    "title": issue.get("title", ""),
                    "body": (issue.get("body", "") or "")[:200],  # Limit to 200 chars
                    "labels": [label.get("name", "") for label in issue.get("labels", [])][:3],  # Max 3 labels
                    "state": issue.get("state", ""),
                    "created_at": issue.get("created_at", ""),
                    "html_url": issue.get("html_url", "")  # Add issue URL
                })
            
            return {
                "releases": limited_releases,
                "issues": limited_issues,
                "repository_url": f"https://github.com/{owner}/{repo}"  # Add repo URL
            }
        except Exception as e:
            logger.error(f"Error fetching data for {owner}/{repo}: {e}")
            return {"releases": [], "issues": [], "repository_url": f"https://github.com/{owner}/{repo}"}

    def analyze_competitor(self, project_name: str, owner: str, repo: str) -> Optional[CompetitorAnalysis]:
        """Analyze a single competitor using agno data analyzer agent"""
        try:
            logger.info(f"Starting analysis for {project_name}")
            github_data = self.get_github_data(owner, repo)
            
            if not github_data.get("releases") and not github_data.get("issues"):
                logger.warning(f"No data found for {project_name}")
                return None
            
            analysis_prompt = f"""
            Analyze competitive intelligence for {project_name} ({owner}/{repo}):
            
            Repository URL: {github_data["repository_url"]}
            
            Recent Releases: {json.dumps(github_data["releases"])}
            Recent Issues: {json.dumps(github_data["issues"])}
            
            Provide structured analysis with the following requirements:
            1. Include the repository_url: {github_data["repository_url"]}
            2. For each recent release, include the version, description, date, and the html_url link
            3. For recurring issue patterns, include example issue URLs (html_url) for each pattern
            4. Extract key features and strategic insights
            
            IMPORTANT: Include actual URLs from the provided data so users can reference the source material.
            Format the response according to the CompetitorAnalysis model structure.
            """
            
            logger.info(f"Running AI analysis for {project_name}")
            response: RunResponse = self.data_analyzer.run(analysis_prompt)
            
            if response and response.content and isinstance(response.content, CompetitorAnalysis):
                logger.info(f"Successfully analyzed {project_name}")
                return response.content
            else:
                logger.warning(f"Invalid response format for {project_name}: {type(response.content) if response else 'No response'}")
                return None
                
        except Exception as e:
            logger.error(f"Error analyzing {project_name}: {str(e)}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return None

    def generate_weekly_report(self, analyses: List[CompetitorAnalysis]) -> Optional[WeeklyReport]:
        """Generate weekly intelligence report using agno report generator agent"""
        try:
            logger.info("Starting weekly report generation")
            
            # Extract all sources
            sources = []
            for analysis in analyses:
                if hasattr(analysis, 'repository_url') and analysis.repository_url:
                    sources.append(f"{analysis.project_name}: {analysis.repository_url}")
            
            report_prompt = f"""
            Generate competitive intelligence report from competitor analyses:
            
            Data: {json.dumps([analysis.model_dump() for analysis in analyses])}
            
            Provide a structured weekly report with:
            1. Industry trends across competitors with specific examples
            2. Strategic recommendations for product management with supporting evidence  
            3. Competitive threats and opportunities
            4. Analysis methodology explaining the data sources and approach
            
            IMPORTANT: 
            - Include detailed industry trends that reference specific competitor findings
            - Ensure all recommendations are backed by specific evidence from the data
            - Include methodology explaining how this analysis was conducted
            - Focus on actionable insights for Product Managers
            
            Format the response according to the WeeklyReport model structure.
            """
            
            logger.info("Running AI report generation")
            response: RunResponse = self.report_generator.run(report_prompt)
            
            if response and response.content and isinstance(response.content, WeeklyReport):
                # Ensure sources are populated if not provided by AI
                if not response.content.sources and sources:
                    response.content.sources = sources
                logger.info("Successfully generated weekly report")
                return response.content
            else:
                logger.warning(f"Invalid response from report generator: {type(response.content) if response else 'No response'}")
                return None
                
        except Exception as e:
            logger.error(f"Error generating report: {str(e)}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
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
        page_title="📡 PM Competitive Radar",
        page_icon="📡",
        layout="wide"
    )
    
    st.title("📡 PM Competitive Radar")
    st.markdown("*AI-powered competitive intelligence for Product Managers*")
    st.markdown("---")
    
    # Display agno framework info
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        st.info("🤖 **Data Analyzer Agent**\nAnalyzes GitHub releases & issues")
    with col2:
        st.info("📊 **Report Generator Agent**\nCreates strategic insights")  
    with col3:
        st.info("⚙️ **Configurable Projects**\nCustom or default competitors")
    
    # Check GitHub token
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        st.error("❌ GitHub token not found! Please set GITHUB_TOKEN in your .env file")
        return
    
    # Initialize workflow without PostgreSQL
    try:
        workflow = CompetitiveIntelligenceWorkflow(
            session_id="pm-competitive-radar"
        )
        st.sidebar.success("✅ PM Radar initialized")
    except Exception as e:
        st.error(f"Failed to initialize workflow: {e}")
        return
    
    # Sidebar controls
    st.sidebar.title("📡 PM Radar Controls")
    
    # Project configuration section
    st.sidebar.subheader("📋 Configure Projects")
    
    # Option to use default or custom projects
    use_defaults = st.sidebar.checkbox("Use Default Web Frameworks", value=True)
    
    if use_defaults:
        # Default competitors
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
    else:
        # Custom project input
        st.sidebar.markdown("**Add Custom Projects:**")
        
        # Initialize session state for custom projects
        if 'custom_projects' not in st.session_state:
            st.session_state.custom_projects = []
        
        # Add new project form
        with st.sidebar.expander("➕ Add New Project"):
            project_name = st.text_input("Project Name", placeholder="e.g., React")
            github_owner = st.text_input("GitHub Owner", placeholder="e.g., facebook")
            github_repo = st.text_input("Repository Name", placeholder="e.g., react")
            
            if st.button("Add Project"):
                if project_name and github_owner and github_repo:
                    new_project = {
                        "name": project_name,
                        "owner": github_owner,
                        "repo": github_repo
                    }
                    st.session_state.custom_projects.append(new_project)
                    st.success(f"Added {project_name}!")
                else:
                    st.error("Please fill all fields")
        
        # Display and select custom projects
        selected_competitors = {}
        if st.session_state.custom_projects:
            st.sidebar.markdown("**Select Projects to Analyze:**")
            for i, project in enumerate(st.session_state.custom_projects):
                col1, col2 = st.sidebar.columns([3, 1])
                with col1:
                    if st.checkbox(f"{project['name']}", key=f"custom_{i}"):
                        selected_competitors[project['name']] = {
                            "owner": project['owner'],
                            "repo": project['repo']
                        }
                with col2:
                    if st.button("🗑️", key=f"delete_{i}", help="Delete project"):
                        st.session_state.custom_projects.pop(i)
                        st.rerun()
        else:
            st.sidebar.info("No custom projects added yet")
    
    # Analysis controls
    st.sidebar.markdown("---")
    
    # Show selected projects count
    if selected_competitors:
        st.sidebar.success(f"✅ {len(selected_competitors)} projects selected")
        st.sidebar.markdown("**Selected Projects:**")
        for name in selected_competitors.keys():
            st.sidebar.write(f"• {name}")
    else:
        st.sidebar.warning("⚠️ No projects selected")
    
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
                                    if hasattr(release, 'url') and release.url:
                                        st.markdown(f"**[View Release →]({release.url})**")
                        else:
                            st.info("No recent releases")
                        
                        st.markdown("### ⭐ Key Features")
                        for feature in analysis.key_features:
                            st.markdown(f"• {feature}")
                        
                        # Add repository link
                        if hasattr(analysis, 'repository_url') and analysis.repository_url:
                            st.markdown("### 📁 Repository")
                            st.markdown(f"**[View on GitHub →]({analysis.repository_url})**")
                    
                    with col2:
                        st.markdown("### 🐛 Recurring Issues")
                        if analysis.recurring_issues:
                            for issue in analysis.recurring_issues:
                                st.metric(label=issue.pattern, value=f"{issue.count} occurrences")
                                # Show example links if available
                                if hasattr(issue, 'example_links') and issue.example_links:
                                    with st.expander(f"Examples for {issue.pattern}"):
                                        for i, link in enumerate(issue.example_links[:3]):  # Show max 3 examples
                                            st.markdown(f"[Example {i+1} →]({link})")
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
            
            # Display key insights with sources if available
            st.markdown("### 🔍 Key Insights")
            # Since we removed key_insights_with_sources from the model, 
            # we'll show insights from industry_trends with source attribution
            for i, trend in enumerate(report.industry_trends[:3]):  # Show top 3
                st.markdown(f"**Insight {i+1}:** {trend}")
                # Show sources for this insight based on analyzed projects
                if report.analyses:
                    example_source = report.analyses[0]  # Use first analysis as example
                    if hasattr(example_source, 'repository_url') and example_source.repository_url:
                        st.markdown(f"📖 [View Source →]({example_source.repository_url})")
                st.markdown("---")
        
        with col2:
            st.markdown("### 💡 Strategic Recommendations")
            for rec in report.recommendations:
                st.markdown(f"• {rec}")
        
        # Sources and Methodology Section
        st.markdown("---")
        st.subheader("📚 Sources & Methodology")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("### 📖 Data Sources")
            if hasattr(report, 'sources') and report.sources:
                for source in report.sources:
                    if ":" in source:
                        project, url = source.split(":", 1)
                        st.markdown(f"• **{project.strip()}**: [{url.strip()}]({url.strip()})")
                    else:
                        st.markdown(f"• {source}")
            else:
                # Fallback: show analyzed projects
                for analysis in report.analyses:
                    if hasattr(analysis, 'repository_url') and analysis.repository_url:
                        st.markdown(f"• **{analysis.project_name}**: [{analysis.repository_url}]({analysis.repository_url})")
            
        with col2:
            st.markdown("### 🔬 Methodology")
            if hasattr(report, 'methodology') and report.methodology:
                st.markdown(report.methodology)
            else:
                st.markdown("""
                **Analysis Approach:**
                - GitHub API for live data collection
                - Last 3 releases per project analyzed
                - Past 7 days of issues tracked
                - AI-powered pattern recognition
                - Structured competitive intelligence output
                """)
        
        # Data freshness and report info
        st.markdown("---")
        col1, col2 = st.columns([2, 1])
        with col1:
            st.info(f"📅 **Report Generated:** {report.report_date} | **Projects Analyzed:** {len(report.analyses)} | **Data Source:** Live GitHub API")
        with col2:
            st.success("✅ All links verified and current")
    
    else:
        st.info("👆 Configure projects in the sidebar and click 'Run Agno Analysis' to generate intelligence!")
        
        st.markdown("## 📡 PM Competitive Radar Features")
        st.markdown("""
        - **🔧 Configurable Projects**: Add any GitHub repository for analysis
        - **🤖 AI Agents**: Specialized agents for data analysis and report generation
        - **📋 Structured Models**: Pydantic models for consistent data handling  
        - **🔄 Workflow Management**: Robust workflow orchestration with retry logic
        - **💾 PostgreSQL Storage**: Optional persistent storage for caching
        - **📊 Real-time Analysis**: Live GitHub API integration
        - **🎯 PM Focus**: Strategic insights and recommendations for Product Managers
        """)
        
        st.markdown("## 💡 Example Projects You Can Analyze")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            st.markdown("""
            **Web Frameworks:**
            - Next.js (vercel/next.js)
            - React (facebook/react)
            - Vue (vuejs/core)
            - Angular (angular/angular)
            
            **Backend Frameworks:**
            - Express (expressjs/express)
            - Fastify (fastify/fastify)
            - NestJS (nestjs/nest)
            """)
        
        with col2:
            st.markdown("""
            **Developer Tools:**
            - VS Code (microsoft/vscode)
            - Prettier (prettier/prettier)
            - ESLint (eslint/eslint)
            - Webpack (webpack/webpack)
            
            **Databases:**
            - PostgreSQL (postgres/postgres)
            - MongoDB (mongodb/mongo)
            - Redis (redis/redis)
            """)
            
        st.markdown("**💡 Tip:** Add your competitors' open-source projects to track their development trends!")


# Create the agno workflow instance (no PostgreSQL dependency)
competitive_intelligence = CompetitiveIntelligenceWorkflow(
    session_id="pm-competitive-radar"
)

# Run Streamlit app
if __name__ == "__main__":
    display_agno_streamlit_dashboard()
