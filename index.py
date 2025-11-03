from models import User
from collections import defaultdict
import re

def tokenize(text):
    """Tokenize text into lowercase words."""
    if not text:
        return []
    return re.findall(r'\b\w+\b', text.lower())

def build_inverted_index():
    """Build inverted index for alumni users."""
    inverted_index = defaultdict(list)
    alumni = User.query.filter_by(role='alumni').all()
    for user in alumni:
        user_id = user.id
        # Index batch_year
        if user.batch_year:
            inverted_index[str(user.batch_year)].append(user_id)
        # Index skills
        if user.skills:
            skills = tokenize(user.skills)
            for skill in skills:
                inverted_index[skill].append(user_id)
        # Index role (though all alumni, but maybe)
        inverted_index[user.role].append(user_id)
        # Could index username or email, but maybe not for privacy
    return inverted_index

def search_inverted_index(query, inverted_index):
    """Search the inverted index with a query."""
    tokens = tokenize(query)
    if not tokens:
        return set()
    # For simplicity, intersect all token results
    result_sets = [set(inverted_index.get(token, [])) for token in tokens]
    if result_sets:
        results = result_sets[0]
        for s in result_sets[1:]:
            results &= s
        return results
    return set()

# For ranking, perhaps sort by number of matches or something simple.

def rank_results(results, query, inverted_index):
    """Rank results based on relevance."""
    tokens = tokenize(query)
    ranked = []
    for user_id in results:
        score = sum(1 for token in tokens if user_id in inverted_index.get(token, []))
        ranked.append((user_id, score))
    ranked.sort(key=lambda x: x[1], reverse=True)
    return [uid for uid, _ in ranked]