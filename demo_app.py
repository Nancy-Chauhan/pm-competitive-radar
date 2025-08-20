import os
import json
import requests
import streamlit as st
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Mock the agno imports for demo
class MockAgent:
    def __init__(self, name, instructions, response_model=None):
        self.name = name
        self.instructions = instructions
        self.response_model = response_model
    
    def run(self, prompt):
        # Mock response for demo
        class MockResponse:
            def __init__(self, content):
                self.content = content
        
        if "Next.js" in prompt:
            from dataclasses import dataclass
            @dataclass
            class MockAnalysis:
                project_name: str = "Next.js"
                recent_releases: List = []
                key_features: List = ["React Server Components", "App Router improvements"]
                recurring_issues: List = []
            return MockResponse(MockAnalysis())
        
        # Mock report generation
        if "Generate weekly" in prompt:
            from dataclasses import dataclass
            @dataclass 
            class MockReport:
                report_date: str = datetime.now().strftime("%Y-%m-%d")
                analyses: List = []
                industry_trends: List = ["Server-side rendering adoption", "Performance focus"]
                recommendations: List = ["Monitor React ecosystem", "Evaluate build tools"]
            return MockResponse(MockReport())
        
        return MockResponse(None)

class MockWorkflow:
    def __init__(self, session_id, storage=None):
        self.session_id = session_id
        self.session_state = {}

def display_streamlit_dashboard():
    """Streamlit dashboard for competitive intelligence"""
    st.set_page_config(
        page_title="🔍 Competitive Intelligence Dashboard",
        page_icon="🔍",
        layout="wide"
    )
    
    st.title("🔍 Competitive Intelligence Dashboard")
    st.markdown("---")
    
    # Check for GitHub token
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token or github_token == "your_github_token_here":
        st.warning("⚠️ GitHub token not configured!")
        st.info("To get real data, set your GitHub token in the .env file or run: `export GITHUB_TOKEN=your_token`")
        st.markdown("Get a token at: https://github.com/settings/tokens")
    
    # Sidebar controls
    st.sidebar.title("Controls")
    
    demo_mode = st.sidebar.checkbox("Demo Mode (Mock Data)", value=True)
    
    if st.sidebar.button("🔄 Generate New Report", type="primary"):
        with st.spinner("Analyzing competitors..."):
            if demo_mode:
                # Generate mock report for demo
                mock_report_data = {
                    "report_date": datetime.now().strftime("%Y-%m-%d"),
                    "analyses": [
                        {
                            "project_name": "Next.js",
                            "recent_releases": [
                                {"version": "15.2.0", "date": "2025-01-15", "description": "Performance improvements and bug fixes"}
                            ],
                            "key_features": ["React Server Components", "Improved App Router", "Better TypeScript support"],
                            "recurring_issues": [
                                {"pattern": "Build performance", "count": 15},
                                {"pattern": "TypeScript errors", "count": 8}
                            ]
                        },
                        {
                            "project_name": "Nuxt", 
                            "recent_releases": [
                                {"version": "3.15.0", "date": "2025-01-10", "description": "Vue 3.5 support and dev tools improvements"}
                            ],
                            "key_features": ["Vue 3.5 integration", "Better dev tools", "SSR optimizations"],
                            "recurring_issues": [
                                {"pattern": "Hydration mismatches", "count": 12},
                                {"pattern": "Module loading", "count": 6}
                            ]
                        },
                        {
                            "project_name": "SvelteKit",
                            "recent_releases": [
                                {"version": "2.15.0", "date": "2025-01-08", "description": "New adapter features and performance updates"}
                            ],
                            "key_features": ["New adapter system", "Improved routing", "Better error handling"],
                            "recurring_issues": [
                                {"pattern": "Adapter compatibility", "count": 9},
                                {"pattern": "Build issues", "count": 5}
                            ]
                        }
                    ],
                    "industry_trends": [
                        "Increased focus on server-side rendering performance",
                        "Better TypeScript integration across frameworks", 
                        "Improved developer experience and debugging tools",
                        "Enhanced build system optimizations"
                    ],
                    "recommendations": [
                        "Monitor React Server Components adoption in Next.js",
                        "Evaluate Vue 3.5 features for potential opportunities",
                        "Consider SvelteKit's adapter system approach",
                        "Focus on build performance optimizations",
                        "Improve TypeScript developer experience"
                    ]
                }
                st.session_state.current_report = mock_report_data
                st.success("✅ Demo report generated!")
            else:
                st.error("❌ Real data collection requires proper setup")
    
    # Display report if available
    if 'current_report' in st.session_state:
        report = st.session_state.current_report
        
        # Report header
        col1, col2 = st.columns([3, 1])
        with col1:
            st.header(f"📊 Weekly Report - {report['report_date']}")
        with col2:
            st.metric("Competitors Analyzed", len(report['analyses']))
        
        # Competitor Analysis Section
        st.subheader("🏢 Competitor Analysis")
        
        # Create tabs for each competitor
        competitor_names = [analysis['project_name'] for analysis in report['analyses']]
        competitor_tabs = st.tabs(competitor_names)
        
        for tab, analysis in zip(competitor_tabs, report['analyses']):
            with tab:
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.markdown("### 🚀 Recent Releases")
                    if analysis['recent_releases']:
                        for release in analysis['recent_releases']:
                            with st.expander(f"{release['version']} - {release['date']}"):
                                st.write(release['description'])
                    else:
                        st.info("No recent releases")
                    
                    st.markdown("### ⭐ Key Features")
                    for feature in analysis['key_features']:
                        st.markdown(f"• {feature}")
                
                with col2:
                    st.markdown("### 🐛 Recurring Issues")
                    if analysis['recurring_issues']:
                        for issue in analysis['recurring_issues']:
                            st.metric(issue['pattern'], issue['count'], label="occurrences")
                    else:
                        st.info("No significant patterns found")
        
        # Industry Trends Section
        st.markdown("---")
        st.subheader("📈 Industry Trends")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("### 🎯 Key Trends")
            for trend in report['industry_trends']:
                st.markdown(f"• {trend}")
        
        with col2:
            st.markdown("### 💡 Recommendations")
            for rec in report['recommendations']:
                st.markdown(f"• {rec}")
    
    else:
        st.warning("⚠️ No report data available. Click 'Generate New Report' to start analysis.")
        
        # Instructions for setup
        st.markdown("## 🚀 Setup Instructions")
        st.markdown("""
        ### For Demo Mode:
        1. ✅ Click 'Generate New Report' with Demo Mode enabled
        
        ### For Real Data:
        1. Get a GitHub token: https://github.com/settings/tokens
        2. Set it in .env file: `GITHUB_TOKEN=your_token_here`
        3. Disable Demo Mode and generate report
        
        ### Full Setup (with agno framework):
        1. Install PostgreSQL
        2. Set up database connection in .env
        3. Configure agno framework
        """)

if __name__ == "__main__":
    display_streamlit_dashboard()
