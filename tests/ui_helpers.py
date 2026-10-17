"""Label-based navigation survives moving controls into the sidebar."""
def click(app,label):
    navigation={'Batch scheduling simulator':'Scheduling simulator',
        'Open Daily resource monitoring (separate synthetic dataset)':'Daily resource monitoring',
        'Copilot and supervisor review':'Copilot','Return to Sitara views':'Orders'}
    if label in navigation:
        navigate(app,navigation[label])
    else:next(b for b in app.button if b.label==label).click().run(timeout=40)
    return app


def navigate(app,target):
    secondary=target in ('Copilot','Resource analysis','Daily resource monitoring')
    next(r for r in app.radio if r.label=='Workspace').set_value('More tools' if secondary else target).run(timeout=40)
    if secondary:next(s for s in app.selectbox if s.label=='More tools').set_value(target).run(timeout=40)
    return app
