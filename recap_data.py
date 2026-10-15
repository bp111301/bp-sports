"""Verified postgame facts for presentation only; no forecast or grading writes."""
from game_status import espn_game, nhl_game, matches, score
from preview_data import stamp, team

def verified_final(actual, expected):
    return bool(matches(actual, expected['sport'], expected['home_team'], expected['away_team'])
                and actual['state']=='final' and expected.get('state')=='final'
                and all(actual[k]==expected.get(k) for k in ('home_score','away_score'))
                and stamp(actual['start_time_utc'])==stamp(expected.get('start_time_utc')))

def period_story(home, away, home_scores, away_scores, sport):
    if len(home_scores)!=len(away_scores) or not home_scores:return None
    values=[(score(h),score(a)) for h,a in zip(home_scores,away_scores)]
    if any(h is None or a is None for h,a in values):return None
    index=0 if sport=='NHL' else 1
    if len(values)<=index:return None
    h=sum(v[0] for v in values[:index+1]);a=sum(v[1] for v in values[:index+1])
    point='after the first period' if sport=='NHL' else 'at halftime'
    if h==a:return f'The teams were tied {h}–{a} {point}.'
    lead=home if h>a else away
    return f'{lead} led {max(h,a)}–{min(h,a)} {point}.'

def espn_recap(sport, payload, expected, checked):
    actual=espn_game(sport,payload.get('header',{}),checked)
    if not verified_final(actual,expected):return None
    c=payload['header']['competitions'][0];sides={v['homeAway']:v for v in c['competitors']}
    flow=period_story(expected['home_team'],expected['away_team'],
        [v.get('value',v.get('displayValue')) for v in sides['home'].get('linescores',[])],
        [v.get('value',v.get('displayValue')) for v in sides['away'].get('linescores',[])],sport)
    facts=[];stats={}
    wanted={'totalYards':'total yards','rushingYards':'rushing yards','turnovers':'turnovers','thirdDownEff':'third-down conversions'} if sport in ('NFL','CFB') else {'fieldGoalPct':'field-goal percentage','threePointFieldGoalPct':'three-point percentage','rebounds':'rebounds','turnovers':'turnovers'}
    for side in payload.get('boxscore',{}).get('teams',[]):
        name=side.get('team',{}).get('location') if sport=='CFB' else side.get('team',{}).get('abbreviation')
        if team(sport,name) not in (team(sport,expected['home_team']),team(sport,expected['away_team'])):continue
        stats[team(sport,name)]={v['name']:str(v.get('displayValue','')) for v in side.get('statistics',[]) if v.get('name') in wanted}
    for key,label in wanted.items():
        h=stats.get(team(sport,expected['home_team']),{}).get(key);a=stats.get(team(sport,expected['away_team']),{}).get(key)
        if h and a:facts.append(f"{expected['away_team']} finished with {a} {label}; {expected['home_team']} recorded {h}.")
    # Summarize box-score rows directly rather than copying a publisher's article.
    leaders=[]
    for side in payload.get('boxscore',{}).get('players',[]):
        name=side.get('team',{}).get('location') if sport=='CFB' else side.get('team',{}).get('abbreviation')
        if team(sport,name) not in (team(sport,expected['home_team']),team(sport,expected['away_team'])):continue
        for category in side.get('statistics',[]):
            kind=category.get('name');keys=category.get('keys',[])
            primary={'passing':'passingYards','rushing':'rushingYards','receiving':'receivingYards'}.get(kind)
            if sport=='NBA':primary='points'
            if primary not in keys:continue
            idx=keys.index(primary);rows=[]
            for player in category.get('athletes',[]):
                values=player.get('stats',[])
                try:value=float(values[idx])
                except (ValueError,IndexError,TypeError):continue
                if value>=0:rows.append((value,player,dict(zip(keys,values))))
            if not rows:continue
            _,player,values=max(rows,key=lambda x:x[0]);athlete=player.get('athlete',{}).get('displayName')
            if not athlete:continue
            if sport=='NBA':text=f"{athlete} ({name}) scored {values[primary]} points"
            elif kind=='passing':text=f"{athlete} ({name}) threw for {values[primary]} yards"
            elif kind=='rushing':text=f"{athlete} ({name}) ran for {values[primary]} yards"
            else:text=f"{athlete} ({name}) had "+(f"{values['receptions']} catches for " if 'receptions' in values else '')+f"{values[primary]} receiving yards"
            td={'passing':'passingTouchdowns','rushing':'rushingTouchdowns','receiving':'receivingTouchdowns'}.get(kind)
            if td in values and score(values[td]):text+=f" and {values[td]} "+('touchdown' if score(values[td])==1 else 'touchdowns')
            leaders.append(text+'.')
    return {**expected,'checked_at_utc':checked,'flow':flow,'facts':facts,'leaders':leaders[:6],
            'finish':str(c.get('status',{}).get('type',{}).get('shortDetail','Final')),
            'sources':[{'name':'ESPN box score','url':expected['source_url']}], 'detailed':bool(facts or leaders),'version':2}

def nhl_recap(payload, expected, checked, landing=None):
    actual=nhl_game(payload,checked)
    if not verified_final(actual,expected):return None
    facts=[];leaders=[];landing=landing or {};periods=landing.get('summary',{}).get('scoring',[])
    # Scoring groups describe one period each. Never infer flow from a partial group.
    flow=None
    if periods:
        first=next((v for v in periods if v.get('periodDescriptor',{}).get('number')==1),None)
        if first is not None:
            goals=first.get('goals',[])
            if goals:
                last=goals[-1]
                if all(score(last.get(k)) is not None for k in ('homeScore','awayScore')):
                    flow=period_story(expected['home_team'],expected['away_team'],[last['homeScore']],[last['awayScore']],'NHL')
    for side,field in [('away','awayTeam'),('home','homeTeam')]:
        name=expected[side+'_team'];sog=score(payload.get(field,{}).get('sog'))
        if sog is not None:facts.append(f'{name} put {sog} shots on goal.')
        players=payload.get('playerByGameStats',{}).get(field,{})
        skaters=players.get('forwards',[])+players.get('defense',[])
        if skaters:
            best=max(skaters,key=lambda p:(score(p.get('points')) or 0,score(p.get('goals')) or 0))
            n=best.get('name',{});n=n.get('default') if isinstance(n,dict) else n
            if n and all(score(best.get(k)) is not None for k in ('goals','assists')):
                goals,assists=score(best['goals']),score(best['assists'])
                leaders.append(f"{n} ({name}) finished with {goals} "+('goal' if goals==1 else 'goals')+f" and {assists} "+('assist' if assists==1 else 'assists')+'.')
        for goalie in players.get('goalies',[]):
            n=goalie.get('name',{});n=n.get('default') if isinstance(n,dict) else n
            saves=score(goalie.get('saves'));faced=score(goalie.get('shotsAgainst'))
            if n and saves is not None and faced and saves<=faced:leaders.append(f'{n} ({name}) stopped {saves} of {faced} shots.')
    finish={'OT':'Final/OT','SO':'Final/SO'}.get(payload.get('periodDescriptor',{}).get('periodType'),'Final')
    return {**expected,'checked_at_utc':checked,'flow':flow,'facts':facts,'leaders':leaders,
            'finish':finish,'sources':[{'name':'NHL game center','url':expected['source_url']}],'detailed':bool(facts or leaders),'version':2}

def recap_paragraphs(recap):
    h,a=recap['home_score'],recap['away_score'];home,away=recap['home_team'],recap['away_team']
    extra=' in overtime' if 'OT' in recap.get('finish','').upper() else ' in a shootout' if recap.get('finish')=='Final/SO' else ''
    intro=f'{away} and {home} finished tied {a}–{h}.' if h==a else f'{home if h>a else away} beat {away if h>a else home} {max(h,a)}–{min(h,a)}{extra}.'
    out=[intro+(' '+recap['flow'] if recap.get('flow') else '')]
    if recap.get('facts'):out.append(' '.join(recap['facts']))
    if recap.get('leaders'):out.append(' '.join(recap['leaders']))
    if not recap.get('detailed'):out.append('The final score is verified. Detailed game stats are not available yet, so a fuller recap is pending.')
    return out
