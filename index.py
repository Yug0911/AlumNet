from models import User
from collections import defaultdict
import re

def tokenize(text):
    """Tokenize text into lowercase words."""
    if not text:
        return []
    return re.findall(r'\b\w+\b', text.lower())

def build_inverted_index():
    """Build inverted index for all users."""
    inverted_index = defaultdict(list)
    users = User.query.all()
    for user in users:
        user_id = user.id
        # Index batch_year
        if user.batch_year:
            inverted_index[str(user.batch_year)].append(user_id)
        # Index skills
        if user.skills:
            skills = tokenize(user.skills)
            for skill in skills:
                inverted_index[skill].append(user_id)
        # Index role
        inverted_index[user.role].append(user_id)
        # Index username (tokenized for name search)
        if user.username:
            name_tokens = tokenize(user.username)
            for token in name_tokens:
                inverted_index[token].append(user_id)
    return inverted_index

def search_inverted_index(query, inverted_index):
    """Search the inverted index with a query."""
    tokens = tokenize(query)
    if not tokens:
        return set()
    # Use union (OR) instead of intersection (AND) for better search results
    result_sets = [set(inverted_index.get(token, [])) for token in tokens]
    if result_sets:
        results = set()
        for s in result_sets:
            results |= s
        return results
    return set()

# For ranking, perhaps sort by number of matches or something simple.

def rank_results(results, query, inverted_index):
    """Rank results based on relevance."""
    tokens = tokenize(query)
    ranked = []
    for user_id in results:
        score = 0
        for token in tokens:
            if user_id in inverted_index.get(token, []):
                # Give higher weight to exact matches
                score += 2
            # Check for partial matches in skills or names
            for key, user_ids in inverted_index.items():
                if token.lower() in key.lower() and user_id in user_ids:
                    score += 1
        ranked.append((user_id, score))
    ranked.sort(key=lambda x: x[1], reverse=True)
    return [uid for uid, _ in ranked]