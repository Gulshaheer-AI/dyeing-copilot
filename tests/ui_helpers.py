"""Label-based navigation survives moving controls into the sidebar."""
def click(app,label):
    navigation={'Batch scheduling simulator':'Scheduling simulator',
        'Open Daily resource monitoring (separate synthetic dataset)':'Daily resource monitoring',
        'Copilot and supervisor review':'Copilot','Return to Sitara views':'Orders'}
    if label in navigation:
        next(r for r in app.radio if r.label=='Workspace').set_value(navigation[label]).run(timeout=40)
    else:next(b for b in app.button if b.label==label).click().run(timeout=40)
    return app
