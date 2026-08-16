#!/usr/bin/env python3
"""Fix QB situation grades based on current team_qb board position."""

import json

# Load players
with open('players.json') as f:
    data = json.load(f)

players = data['players']

# Get all QBs sorted by base rating
qbs = sorted([p for p in players if p['pos'] == 'QB'], key=lambda x: x['base'], reverse=True)

# Create QB name to rank mapping
qb_to_rank = {}
for i, qb in enumerate(qbs, 1):
    qb_to_rank[qb['player']] = i

print("QB Tiers:")
print("\nELITE (QB1-8):")
for i in range(min(8, len(qbs))):
    qb = qbs[i]
    print(f"  QB{i+1}: {qb['player']} (base {qb['base']:.1f})")

print("\nAVERAGE (QB9-18):")
for i in range(8, min(18, len(qbs))):
    qb = qbs[i]
    print(f"  QB{i+1}: {qb['player']} (base {qb['base']:.1f})")

print("\nWEAKNESS (QB19+):")
for i in range(18, min(25, len(qbs))):
    qb = qbs[i]
    print(f"  QB{i+1}: {qb['player']} (base {qb['base']:.1f})")

# Function to grade QB
def grade_qb(qb_name, qb_obj=None):
    if not qb_name or qb_name == "-":
        return "unproven"
    
    rank = qb_to_rank.get(qb_name)
    if rank is None:
        return "unproven"
    
    # Check if rookie/unproven (minimal games)
    if qb_obj:
        games = qb_obj.get('games_played', 0)
        sample_note = qb_obj.get('sample_note', '')
        if games == 0 or 'Rookie' in sample_note:
            return "unproven"
    
    if rank <= 8:
        return "elite"
    elif rank <= 18:
        return "average"
    else:
        return "weakness"

# Update all skill players
updates = []
for p in players:
    if p['pos'] in ['RB', 'WR', 'TE']:
        team_qb = p.get('team_qb')
        old_situation = p.get('qb_situation')
        
        # Find the QB object to check games
        qb_obj = next((q for q in qbs if q['player'] == team_qb), None)
        new_situation = grade_qb(team_qb, qb_obj)
        
        if old_situation != new_situation:
            updates.append({
                'player': p['player'],
                'pos': p['pos'],
                'team': p.get('team'),
                'team_qb': team_qb,
                'old': old_situation,
                'new': new_situation,
                'qb_rank': qb_to_rank.get(team_qb, '?')
            })
            p['qb_situation'] = new_situation

# Save updated data
with open('players.json', 'w') as f:
    json.dump(data, f, indent=2)

print(f"\n\nUpdated {len(updates)} players:")
for u in sorted(updates, key=lambda x: x['qb_rank'] if isinstance(x['qb_rank'], int) else 999):
    print(f"  {u['player']:25s} ({u['pos']}, {u['team']}): {u['old']:10s} -> {u['new']:10s} (QB {u['team_qb']}, rank {u['qb_rank']})")

print(f"\nSaved to players.json")
