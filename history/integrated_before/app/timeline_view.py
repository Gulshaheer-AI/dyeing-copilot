"""Readable daily timeline; continuous time and exact exported event timestamps."""
from datetime import datetime,timedelta
from html import escape
import altair as alt
import streamlit as st
from app.planner_presentation import timeline_rows,clip_timeline,useful_window,machine_name,shift_day
from planner.change_requests import digest


def render_timeline(case,run):
    with st.container(key='dashboard_timeline'):
        st.subheader('Machine activity',anchor=False)
        frame,lo,hi=timeline_rows(case.orders,case.config,run.schedule)
        ids=[m.virtual_id for m in case.config.machines]
        with st.container(horizontal=True,wrap=True,vertical_alignment='bottom'):
            machines=st.multiselect('Machines',ids,default=ids,format_func=machine_name,key='timeline_machines',width=680)
            full=st.checkbox('Show full schedule',key='timeline_full',width='content')
        if not machines:st.info('Select a machine to inspect its activity.');return
        default,_=useful_window(frame,lo,hi,machines)
        key=digest({'case':case.fingerprint,'schedule':run.schedule,'machines':machines})[:20]
        cursor_key,date_key='timeline_start_'+key,'timeline_date_'+key
        if cursor_key not in st.session_state:st.session_state[cursor_key]=default
        if date_key not in st.session_state:st.session_state[date_key]=st.session_state[cursor_key].date()
        def move(offset):
            st.session_state[cursor_key]=shift_day(st.session_state[cursor_key],lo,hi,offset)
            st.session_state[date_key]=st.session_state[cursor_key].date()
        def pick_date():
            if st.session_state[date_key] is None:return
            chosen=datetime.combine(st.session_state[date_key],datetime.min.time())
            st.session_state[cursor_key]=shift_day(chosen,lo,hi,0)
        with st.container(horizontal=True,wrap=True,vertical_alignment='bottom'):
            st.button('Previous day',icon=':material/chevron_left:',on_click=move,args=(-1,),disabled=full or st.session_state[cursor_key]<=lo)
            st.date_input('Timeline start date',value=None,key=date_key,on_change=pick_date,disabled=full,width=240)
            st.button('Next day',icon=':material/chevron_right:',on_click=move,args=(1,),
                disabled=full or st.session_state[cursor_key]+timedelta(hours=24)>=hi)
        start=lo if full else st.session_state[cursor_key]
        end=hi if full else min(hi,start+timedelta(hours=24))
        if not full and st.session_state[date_key] is None:st.info('Choose a start date.');return
        st.write(f'**{start:%d %b %Y, %H:%M:%S} → {end:%d %b %Y, %H:%M:%S}** · Scenario time, Asia/Karachi')
        data=clip_timeline(frame,start,end,machines)
        # Report actual production/cleaning absence, independently of grey unavailability.
        active=set(data.loc[data.activity!='Unavailable','machine_id'])
        inactive=[machine_name(m) for m in machines if m not in active]
        if inactive:st.write('No production or cleaning in this window: '+', '.join(inactive)+'.')
        if data.empty:
            st.info('No activity in this window. Select another day or show the full schedule.')
            return
        data['exact_start']=data.start.map(lambda t:t.isoformat())
        data['exact_end']=data.end.map(lambda t:t.isoformat())
        # Short blocks retain hover details; full-horizon labels cannot fit truthfully.
        data['centre']=data.visible_start+(data.visible_end-data.visible_start)/2
        data['show_label']=(data.visible_end-data.visible_start).dt.total_seconds()/(end-start).total_seconds()>=.025
        names=[machine_name(m) for m in machines]
        base=alt.Chart(data).encode(y=alt.Y('machine:N',title=None,sort=names,
            scale=alt.Scale(domain=names),axis=alt.Axis(labelLimit=0,labelFontSize=15,labelPadding=12)),
            x=alt.X('visible_start:T',title='Time',scale=alt.Scale(domain=[start.isoformat(),end.isoformat()]),
                axis=alt.Axis(format='%d %b %H:%M' if full else '%H:%M',labelFontSize=13,titleFontSize=13,
                    tickCount=alt.ExprRef(expr='max(2, floor(width / 110))'))),
            x2='visible_end:T',tooltip=[alt.Tooltip('order_id:N',title='Order'),alt.Tooltip('machine_id:N',title='Machine ID'),
                alt.Tooltip('activity:N',title='Activity / cleaning status'),alt.Tooltip('exact_start:N',title='Start'),
                alt.Tooltip('exact_end:N',title='End')])
        palette={'Production':'#0F8A83','Cleaning':'#EDBA54','Terminal cleaning':'#B98128','Unavailable':'#D7DDE5'}
        bars=base.mark_bar(size=36,cornerRadius=3).encode(color=alt.Color('activity:N',title=None,
            scale=alt.Scale(domain=list(palette),range=list(palette.values())),legend=None))
        labels=base.transform_filter((alt.datum.activity=='Production')&alt.datum.show_label).mark_text(
            color='white',fontSize=14,fontWeight='bold',clip=True).encode(x='centre:T',text='label:N')
        chart=(bars+labels).properties(height=max(240,76*len(machines)),background='white').configure_axis(
            labelColor='#394D65',titleColor='#526379',gridColor='#E8EDF3').configure_view(stroke=None).interactive()
        # A documented non-wrapping container scrolls on narrow screens instead
        # of shrinking long machine names and 24 hours into an unreadable sliver.
        with st.container(horizontal=True,wrap=False):
            st.altair_chart(chart,width=860,theme=None)
        st.html('<div class="dc-legend">'+''.join(
            f'<span class="dc-legend-item"><i class="dc-swatch" style="background:{escape(color,quote=True)}"></i>{escape(label)}</span>'
            for label,color in palette.items())+'</div>')
        st.caption('Continuous time: gaps are idle time. Grey blocks are unavailable. Hover shows exact timestamps and short-block order IDs. Scroll horizontally on narrow screens; drag or scroll within the chart to zoom.')
