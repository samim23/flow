# app/analytics/experiments.py
"""
Experiment and Goal Tracking via Markdown Files

Experiments and goals are stored as markdown files with YAML frontmatter.
This allows both humans and AI to easily read/write them.
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

try:
    import frontmatter
except ImportError:
    frontmatter = None
    logger.warning("python-frontmatter not installed, experiment tracking disabled")


@dataclass
class Experiment:
    """An experiment with hypothesis and tracked metrics"""
    path: Path
    title: str
    hypothesis: str
    status: str  # running, completed, cancelled
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    posts: List[str]
    track_metrics: List[str]
    baseline: Dict[str, float]
    content: str  # markdown body
    results_summary: Optional[str] = None  # Summary of results when completed
    winner: Optional[str] = None  # "treatment", "control", or None
    
    @property
    def is_active(self) -> bool:
        return self.status == "running"
    
    @property
    def days_running(self) -> int:
        if not self.start_date:
            return 0
        return (datetime.now() - self.start_date).days


@dataclass
class Goal:
    """A measurable goal with target and deadline"""
    path: Path
    title: str
    target_metric: str
    target_value: float
    current_value: float
    deadline: Optional[datetime]
    status: str  # in_progress, achieved, missed, cancelled
    priority: str  # high, medium, low
    content: str  # markdown body
    
    @property
    def progress_percent(self) -> float:
        if self.target_value == 0:
            return 0
        return min(100, (self.current_value / self.target_value) * 100)
    
    @property
    def days_remaining(self) -> int:
        if not self.deadline:
            return -1
        return (self.deadline - datetime.now()).days


class ExperimentManager:
    """
    Manages experiments and goals stored as markdown files.
    
    Files are stored in:
    - content/experiments/*.md
    - content/goals/*.md
    """
    
    def __init__(self, data_dir: str = None):
        # Default to app/analytics/data/
        if data_dir is None:
            self.data_dir = Path(__file__).parent / "data"
        else:
            self.data_dir = Path(data_dir)
        
        self.experiments_dir = self.data_dir / "experiments"
        self.goals_dir = self.data_dir / "goals"
        
        # Ensure directories exist
        self.experiments_dir.mkdir(parents=True, exist_ok=True)
        self.goals_dir.mkdir(parents=True, exist_ok=True)
    
    def _parse_date(self, value: Any) -> Optional[datetime]:
        """Parse date from frontmatter (could be string, date, or datetime object)"""
        from datetime import date
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            # Convert date to datetime
            return datetime.combine(value, datetime.min.time())
        if isinstance(value, str):
            try:
                return datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                return None
        return None
    
    def get_experiments(self, status: Optional[str] = None) -> List[Experiment]:
        """
        Get all experiments, optionally filtered by status.
        
        Args:
            status: Filter by status (running, completed, cancelled)
        """
        if not frontmatter:
            return []
        
        experiments = []
        
        for path in self.experiments_dir.glob("*.md"):
            # Skip template files (starting with _)
            if path.name.startswith("_"):
                continue
            try:
                post = frontmatter.load(path)
                
                exp = Experiment(
                    path=path,
                    title=post.get("title", path.stem),
                    hypothesis=post.get("hypothesis", ""),
                    status=post.get("status", "running"),
                    start_date=self._parse_date(post.get("start_date")),
                    end_date=self._parse_date(post.get("end_date")),
                    posts=post.get("posts", []),
                    track_metrics=post.get("track_metrics", []),
                    baseline=post.get("baseline", {}),
                    content=post.content,
                    results_summary=post.get("results_summary"),
                    winner=post.get("winner")
                )
                
                if status is None or exp.status == status:
                    experiments.append(exp)
                    
            except Exception as e:
                logger.error(f"Failed to parse experiment {path}: {e}")
        
        # Sort by start date (newest first)
        experiments.sort(key=lambda e: e.start_date or datetime.min, reverse=True)
        return experiments
    
    def get_experiment(self, filename: str) -> Optional[Experiment]:
        """Get a specific experiment by filename"""
        experiments = self.get_experiments()
        for exp in experiments:
            if exp.path.stem == filename or exp.path.name == filename:
                return exp
        return None
    
    def get_goals(self, status: Optional[str] = None) -> List[Goal]:
        """
        Get all goals, optionally filtered by status.
        
        Args:
            status: Filter by status (in_progress, achieved, missed, cancelled)
        """
        if not frontmatter:
            return []
        
        goals = []
        
        for path in self.goals_dir.glob("*.md"):
            # Skip template files (starting with _)
            if path.name.startswith("_"):
                continue
            try:
                post = frontmatter.load(path)
                
                goal = Goal(
                    path=path,
                    title=post.get("title", path.stem),
                    target_metric=post.get("target_metric", ""),
                    target_value=float(post.get("target_value", 0)),
                    current_value=float(post.get("current_value", 0)),
                    deadline=self._parse_date(post.get("deadline")),
                    status=post.get("status", "in_progress"),
                    priority=post.get("priority", "medium"),
                    content=post.content
                )
                
                if status is None or goal.status == status:
                    goals.append(goal)
                    
            except Exception as e:
                logger.error(f"Failed to parse goal {path}: {e}")
        
        # Sort by priority then deadline
        priority_order = {"high": 0, "medium": 1, "low": 2}
        goals.sort(key=lambda g: (priority_order.get(g.priority, 1), g.deadline or datetime.max))
        return goals
    
    def get_goal(self, filename: str) -> Optional[Goal]:
        """Get a specific goal by filename"""
        goals = self.get_goals()
        for goal in goals:
            if goal.path.stem == filename or goal.path.name == filename:
                return goal
        return None
    
    def update_goal_progress(self, filename: str, current_value: float) -> bool:
        """
        Update the current_value of a goal.
        
        Args:
            filename: Goal filename (without .md)
            current_value: New current value
            
        Returns:
            True if updated successfully
        """
        if not frontmatter:
            return False
        
        goal_path = self.goals_dir / f"{filename}.md"
        if not goal_path.exists():
            goal_path = self.goals_dir / filename
        
        if not goal_path.exists():
            return False
        
        try:
            post = frontmatter.load(goal_path)
            post["current_value"] = current_value
            
            # Check if goal achieved
            target = float(post.get("target_value", 0))
            if current_value >= target:
                post["status"] = "achieved"
            
            with open(goal_path, "w") as f:
                f.write(frontmatter.dumps(post))
            
            return True
        except Exception as e:
            logger.error(f"Failed to update goal {filename}: {e}")
            return False
    
    def complete_experiment(self, filename: str, results: str, winner: str = None, results_summary: str = None) -> bool:
        """
        Mark an experiment as completed and add results.
        
        Args:
            filename: Experiment filename
            results: Results markdown to append to content
            winner: "treatment" or "control" (optional)
            results_summary: Short summary of results (optional)
            
        Returns:
            True if updated successfully
        """
        if not frontmatter:
            return False
        
        exp_path = self.experiments_dir / f"{filename}.md"
        if not exp_path.exists():
            exp_path = self.experiments_dir / filename
        
        if not exp_path.exists():
            return False
        
        try:
            post = frontmatter.load(exp_path)
            post["status"] = "completed"
            post["end_date"] = datetime.now().strftime("%Y-%m-%d")
            
            # Store results metadata in frontmatter
            if results_summary:
                post["results_summary"] = results_summary
            elif results:
                # Extract first line as summary
                post["results_summary"] = results.split('\n')[0][:200]
            
            if winner:
                post["winner"] = winner
            
            # Append results to content
            post.content += f"\n\n## Results (Auto-generated {datetime.now().strftime('%Y-%m-%d')})\n\n{results}"
            
            with open(exp_path, "w") as f:
                f.write(frontmatter.dumps(post))
            
            return True
        except Exception as e:
            logger.error(f"Failed to complete experiment {filename}: {e}")
            return False
    
    def get_experiment_metrics(self, experiment: Experiment) -> Dict[str, Any]:
        """
        Fetch actual metrics for an experiment's posts from analytics.
        
        Returns aggregated metrics for the experiment period.
        """
        from . import get_analytics_store, get_matomo_client
        
        store = get_analytics_store()
        matomo = get_matomo_client()
        
        if not experiment.posts:
            return {"error": "No posts in experiment"}
        
        metrics = {
            "posts_count": len(experiment.posts),
            "posts_data": [],
            "totals": {},
            "averages": {}
        }
        
        total_pageviews = 0
        total_time = 0
        
        for post_path in experiment.posts:
            post_analytics = store.get_post_analytics(post_path)
            if post_analytics:
                metrics["posts_data"].append({
                    "path": post_path,
                    "pageviews": post_analytics.total_pageviews,
                    "avg_time": post_analytics.avg_time_on_page
                })
                total_pageviews += post_analytics.total_pageviews
                total_time += post_analytics.avg_time_on_page
        
        metrics["totals"]["pageviews"] = total_pageviews
        if metrics["posts_data"]:
            metrics["averages"]["pageviews"] = total_pageviews / len(metrics["posts_data"])
            metrics["averages"]["avg_time"] = total_time / len(metrics["posts_data"])
        
        return metrics


# Singleton instance
_experiment_manager: Optional[ExperimentManager] = None

def get_experiment_manager() -> ExperimentManager:
    """Get singleton experiment manager instance"""
    global _experiment_manager
    if _experiment_manager is None:
        from pathlib import Path
        # Use app/analytics/data/ to keep experiments/goals separate from blog content
        analytics_data_dir = Path(__file__).parent / "data"
        _experiment_manager = ExperimentManager(str(analytics_data_dir))
    return _experiment_manager

