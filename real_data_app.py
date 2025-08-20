import os
import json
import requests
import streamlit as st
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import Counter
import re

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

def get_github_data(owner: str, repo: str) -> Dict:
    """Fetch real GitHub data using the API"""
    token = os.getenv("GITHUB_TOKEN")
    headers = {"Authorization": f"token {token}"} if token else {}
    
    releases_url = f"https://api.github.com/repos/{owner}/{repo}/releases"
    issues_url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    
    try:
        # Get recent releases
        releases_response = requests.get(releases_url, headers=headers)
        if releases_response.status_code == 200:
            releases_data = releases_response.json()
        else:
            st.error(f"GitHub API Error {releases_response.status_code} for {owner}/{repo} releases")
            releases_data = []
        
        # Get recent issues (last 7 days)
        cutoff_date = (datetime.now() - timedelta(days=7)).isoformat()
        issues_params = {
            "since": cutoff_date, 
            "state": "all", 
            "per_page": 100,
            "sort": "created"
        }
        issues_response = requests.get(issues_url, headers=headers, params=issues_params)
        if issues_response.status_code == 200:
            issues_data = issues_response.json()
        else:
            st.error(f"GitHub API Error {issues_response.status_code} for {owner}/{repo} issues")
            issues_data = []
        
        return {
            "releases": releases_data[:5],  # Last 5 releases
            "issues": issues_data,
            "status": "success"
        }
        
    except Exception as e:
        st.error(f"Error fetching data for {owner}/{repo}: {e}")
        return {"releases": [], "issues": [], "status": "error"}

def analyze_releases(releases: List[Dict]) -> Dict:
    """Analyze release data to extract key features"""
    recent_releases = []
    key_features = []
    breaking_changes = []
    
    for release in releases:
        if not release.get("draft", False):
            release_info = {
                "version": release.get("tag_name", "Unknown"),
                "date": release.get("published_at", "")[:10] if release.get("published_at") else "",
                "description": release.get("body", "")[:200] + "..." if len(release.get("body", "")) > 200 else release.get("body", "")
            }
            recent_releases.append(release_info)
            
            # Extract features from release notes
            body = release.get("body", "").lower()
            if any(word in body for word in ["feature", "new", "add", "implement"]):
                feature_lines = [line.strip() for line in body.split('\n') 
                               if any(word in line.lower() for word in ["feature", "new", "add", "implement"])]
                key_features.extend(feature_lines[:2])  # Take first 2 feature mentions
            
            # Check for breaking changes
            if any(word in body for word in ["breaking", "deprecated", "removed"]):
                breaking_lines = [line.strip() for line in body.split('\n') 
                                if any(word in line.lower() for word in ["breaking", "deprecated", "removed"])]
                breaking_changes.extend(breaking_lines[:2])
    
    return {
        "recent_releases": recent_releases,
        "key_features": list(set(key_features))[:5],  # Dedupe and limit
        "breaking_changes": list(set(breaking_changes))[:3]
    }

def analyze_issues(issues: List[Dict]) -> Dict:
    """Analyze issues to find patterns"""
    if not issues:
        return {"recurring_issues": [], "critical_bugs": [], "feature_requests": []}
    
    # Categorize issues
    bug_issues = []
    feature_requests = []
    all_titles = []
    
    for issue in issues:
        title = issue.get("title", "")
        labels = [label.get("name", "") for label in issue.get("labels", [])]
        
        all_titles.append(title.lower())
        
        # Categorize by labels or keywords
        if any(label.lower() in ["bug", "error", "crash", "problem"] for label in labels) or \
           any(word in title.lower() for word in ["bug", "error", "crash", "issue", "problem", "broken"]):
            bug_issues.append(title)
        
        if any(label.lower() in ["enhancement", "feature", "request"] for label in labels) or \
           any(word in title.lower() for word in ["feature", "request", "enhancement", "add", "support"]):
            feature_requests.append(title)
    
    # Find recurring patterns in issue titles
    word_counts = Counter()
    for title in all_titles:
        words = re.findall(r'\b\w+\b', title)
        # Focus on technical terms (longer words)
        important_words = [w for w in words if len(w) > 4 and w not in ["issue", "error", "problem"]]
        word_counts.update(important_words)
    
    recurring_patterns = []
    for word, count in word_counts.most_common(5):
        if count > 1:  # Only show patterns that appear more than once
            recurring_patterns.append({"pattern": word.capitalize(), "count": count})
    
    return {
        "recurring_issues": recurring_patterns,
        "critical_bugs": bug_issues[:5],  # Top 5 bug reports
        "feature_requests": feature_requests[:5]  # Top 5 feature requests
    }

def display_streamlit_dashboard():
    """Streamlit dashboard for competitive intelligence"""
    st.set_page_config(
        page_title="🔍 Competitive Intelligence Dashboard",
        page_icon="🔍",
        layout="wide"
    )
    
    st.title("🔍 Competitive Intelligence Dashboard")
    st.markdown("*Real-time competitor analysis using GitHub API*")
    st.markdown("---")
    
    # Check GitHub token
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        st.error("❌ GitHub token not found! Please set GITHUB_TOKEN in your .env file")
        return
    
    # Sidebar controls
    st.sidebar.title("⚙️ Controls")
    
    # Competitor selection
    st.sidebar.subheader("Competitors to Analyze")
    
    competitors = {
        "Next.js": {"owner": "vercel", "repo": "next.js", "enabled": True},
        "Nuxt": {"owner": "nuxt", "repo": "nuxt", "enabled": True},
        "SvelteKit": {"owner": "sveltejs", "repo": "kit", "enabled": True},
        "Remix": {"owner": "remix-run", "repo": "remix", "enabled": True},
        "Astro": {"owner": "withastro", "repo": "astro", "enabled": True}
    }
    
    selected_competitors = {}
    for name, config in competitors.items():
        if st.sidebar.checkbox(name, value=config["enabled"]):
            selected_competitors[name] = config
    
    # Analysis controls
    if st.sidebar.button("🔄 Analyze Competitors", type="primary"):
        with st.spinner("Fetching data from GitHub..."):
            analyses = []
            progress_bar = st.progress(0)
            
            for i, (project_name, config) in enumerate(selected_competitors.items()):
                st.write(f"Analyzing {project_name}...")
                
                # Fetch GitHub data
                github_data = get_github_data(config["owner"], config["repo"])
                
                if github_data["status"] == "success":
                    # Analyze releases
                    release_analysis = analyze_releases(github_data["releases"])
                    
                    # Analyze issues  
                    issue_analysis = analyze_issues(github_data["issues"])
                    
                    # Combine analysis
                    analysis = {
                        "project_name": project_name,
                        "recent_releases": release_analysis["recent_releases"],
                        "key_features": release_analysis["key_features"],
                        "breaking_changes": release_analysis["breaking_changes"],
                        "recurring_issues": issue_analysis["recurring_issues"],
                        "critical_bugs": issue_analysis["critical_bugs"],
                        "feature_requests": issue_analysis["feature_requests"],
                        "total_issues": len(github_data["issues"])
                    }
                    analyses.append(analysis)
                
                progress_bar.progress((i + 1) / len(selected_competitors))
            
            # Generate industry insights
            all_features = []
            all_issues = []
            for analysis in analyses:
                all_features.extend(analysis["key_features"])
                all_issues.extend([p["pattern"] for p in analysis["recurring_issues"]])
            
            # Find common trends
            feature_counter = Counter(all_features)
            issue_counter = Counter(all_issues)
            
            industry_trends = [f"Common focus: {feature}" for feature, count in feature_counter.most_common(3) if count > 1]
            if not industry_trends:
                industry_trends = ["Performance optimizations", "Developer experience improvements", "TypeScript support"]
            
            common_issues = [f"Industry-wide: {issue} issues" for issue, count in issue_counter.most_common(3) if count > 1]
            
            # Store in session state
            st.session_state.current_report = {
                "report_date": datetime.now().strftime("%Y-%m-%d"),
                "analyses": analyses,
                "industry_trends": industry_trends,
                "common_issues": common_issues,
                "recommendations": [
                    "Monitor emerging patterns in competitor releases",
                    "Address common industry pain points",
                    "Focus on performance and developer experience",
                    "Stay updated with framework-specific optimizations"
                ]
            }
            
            st.success(f"✅ Analysis complete! {len(analyses)} competitors analyzed.")
    
    # Display report
    if 'current_report' in st.session_state:
        report = st.session_state.current_report
        
        # Report header
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.header(f"📊 Weekly Report - {report['report_date']}")
        with col2:
            st.metric("Competitors", len(report['analyses']))
        with col3:
            total_issues = sum(analysis.get('total_issues', 0) for analysis in report['analyses'])
            st.metric("Total Issues", total_issues)
        
        # Competitor Analysis Section
        st.subheader("🏢 Competitor Analysis")
        
        if report['analyses']:
            # Create tabs for each competitor
            competitor_names = [analysis['project_name'] for analysis in report['analyses']]
            competitor_tabs = st.tabs(competitor_names)
            
            for tab, analysis in zip(competitor_tabs, report['analyses']):
                with tab:
                    col1, col2 = st.columns([1, 1])
                    
                    with col1:
                        st.markdown("### 🚀 Recent Releases")
                        if analysis['recent_releases']:
                            for release in analysis['recent_releases'][:3]:  # Show top 3
                                with st.expander(f"{release['version']} - {release['date']}"):
                                    st.write(release['description'])
                        else:
                            st.info("No recent releases")
                        
                        st.markdown("### ⭐ Key Features")
                        for feature in analysis['key_features'][:5]:
                            st.markdown(f"• {feature}")
                        
                        if analysis['breaking_changes']:
                            st.markdown("### ⚠️ Breaking Changes")
                            for change in analysis['breaking_changes']:
                                st.markdown(f"• {change}")
                    
                    with col2:
                        st.markdown("### 🐛 Recurring Issues")
                        if analysis['recurring_issues']:
                            for issue in analysis['recurring_issues']:
                                st.metric(label=issue['pattern'], value=f"{issue['count']} occurrences")
                        else:
                            st.info("No significant patterns found")
                        
                        st.markdown("### 🚨 Critical Bugs")
                        for bug in analysis['critical_bugs'][:3]:
                            st.markdown(f"• {bug}")
                        
                        st.markdown("### 💡 Feature Requests")  
                        for req in analysis['feature_requests'][:3]:
                            st.markdown(f"• {req}")
        
        # Industry Insights Section
        st.markdown("---")
        st.subheader("📈 Industry Insights")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("### 🎯 Trends")
            for trend in report['industry_trends']:
                st.markdown(f"• {trend}")
            
            if report.get('common_issues'):
                st.markdown("### 🔄 Common Issues")
                for issue in report['common_issues']:
                    st.markdown(f"• {issue}")
        
        with col2:
            st.markdown("### 💡 Recommendations")
            for rec in report['recommendations']:
                st.markdown(f"• {rec}")
    
    else:
        st.info("👆 Click 'Analyze Competitors' to generate your first intelligence report!")
        
        st.markdown("## 🎯 What This Dashboard Does")
        st.markdown("""
        - **📊 Real-time Analysis**: Fetches live data from GitHub API
        - **🔍 Release Tracking**: Monitors new features and breaking changes  
        - **🐛 Issue Patterns**: Identifies recurring problems and requests
        - **📈 Industry Trends**: Spots cross-competitor patterns
        - **💡 Strategic Insights**: Provides actionable recommendations
        """)

if __name__ == "__main__":
    display_streamlit_dashboard()
