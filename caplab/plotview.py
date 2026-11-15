"""Interactive C/Q and per-point plots on a Tk Canvas (anti-aliased through caplab.render)."""
import math
import tkinter as tk
from .plotting import curve_groups
from . import fieldwork_tk as fw
from .render import Painter, mix

# Site palette (RF-FIELDWORK scope traces) for the neon dark theme.
NEON = ['#33D1DE', '#EC5AA5', '#F2C230', '#93D65E', '#9C8CFF', '#FF7A3D', '#5AA9FF', '#6CE3C5']
_PLOT = fw.tk_plot_colors()
THEMES={
 'black':dict(bg=_PLOT['bg'],ink=fw.TEXT,muted=fw.DIM,grid=_PLOT['grid'],axis=fw.LINE,box=fw.PANEL,dim=fw.MUTED,colors=fw.SERIES),
 'white':{'bg':'#ffffff','ink':'#15191e','muted':'#49535e','grid':'#e0e4e8','box':'#eef3f7','dim':'#bac1c9',
          'colors':['#006c8f','#73529d','#427b46','#9f6d16','#a64963','#415c97']},
 # Tank Scan Lab: dark = scope glass with glowing traces, light = clean paper
 'neon':{'bg':fw.PLOT_BG,'ink':'#d5ddd7','muted':'#7f8a83','grid':'#18201d','axis':'#3a4641','box':'#121816','dim':'#2c3532',
         'colors':NEON,'glow':True},
 'light':{'bg':'#ffffff','ink':'#1b2530','muted':'#5d6b78','grid':'#e6eaef','axis':'#9aa6b2','box':'#f4f7fa','dim':'#d3dae1',
          'colors':['#0a8fa0','#c2387f','#b07d00','#3f8f2a','#6a5acd','#d9541e','#2f6fd1','#1f9e87']},
}


def series_color(theme, index, count):
    """Distinct color per curve: the theme palette, or evenly spaced hues for many curves."""
    colors = theme['colors']
    if count <= len(colors):
        return colors[index % len(colors)]
    import colorsys
    light = theme.get('bg', '#000000') > '#808080'
    r, g, b = colorsys.hsv_to_rgb((0.52 + index / float(count)) % 1.0, 0.72 if light else 0.62, 0.72 if light else 1.0)
    return '#{:02x}{:02x}{:02x}'.format(int(r * 255), int(g * 255), int(b * 255))


class CQPlot(tk.Canvas):
    FONT='DejaVu Sans'
    hide_single_legend=False
    antialias=True
    def __init__(self,parent,**kwargs):
        kwargs.setdefault('highlightthickness',0);kwargs.setdefault('background',fw.PLOT_BG);kwargs.setdefault('height',350)
        super().__init__(parent,**kwargs)
        self.rows=[];self.names=[];self.axis='point';self.mode='cartesian';self.filters={};self.theme='black'
        self.selected=None;self.points=[];self.tooltip_text='';self.pending=None;self.titles=None;self.metrics=None;self.include_frequency=True;self.metric_minimums={}
        self.legend_boxes=[];self.curve_labels=[]
        self.bind('<Configure>',lambda e:self.schedule_draw())
        self.bind('<Button-1>',self.select_at)
        self.bind('<Motion>',self.hover)
        self.bind('<Leave>',lambda e:self.clear_tooltip())

    def set_data(self,rows,axis,names,mode,filters=None,titles=None,metrics=None,include_frequency=True):
        self.rows=rows;self.axis=axis;self.names=names;self.mode=mode;self.filters=filters or {};self.titles=titles
        self.metrics=metrics;self.include_frequency=include_frequency;self.draw()

    def set_theme(self,theme):
        self.theme=theme.lower() if theme.lower() in THEMES else 'black';self.configure(background=THEMES[self.theme]['bg']);self.draw()

    def schedule_draw(self):
        if self.pending:self.after_cancel(self.pending)
        self.pending=self.after(60,self.draw)

    def draw(self):
        self.pending=None;self.delete('all');self.points=[];self.tooltip_text='';self.legend_boxes=[]
        w,h=self.winfo_width(),self.winfo_height();theme=THEMES[self.theme]
        if w<30 or h<30:return
        p=Painter(self,theme['bg'],self.antialias);glow=1 if theme.get('glow') else 0;F=self.FONT
        if not self.rows:
            p.text(w/2,h/2,getattr(self,'empty_message','Run an SP sweep to see C / Q data.'),theme['muted'],(F,13));p.flush();return
        axis=self.axis if self.axis in self.rows[0] else ('point' if 'point' in self.rows[0] else 'code')
        groups=curve_groups(self.rows,axis,self.names,self.mode,self.filters,self.include_frequency)
        keys=[label for label,_ in groups]
        if self.selected not in keys:self.selected=None
        titles=self.titles or ('Differential C (fF)','Quality factor Q')
        metrics=self.metrics or [('C_F',titles[0],1e15,'fF'),('Q',titles[1],1,'')]
        for panel,(metric,title,scale,unit) in enumerate(metrics):
            half=w/len(metrics);left=panel*half;x0=left+74;x1=left+half-22;y1=h-58
            single=self.hide_single_legend and len(groups)==1
            legend_lines=0 if single else min(4,len(groups));y0=min(48 if single else 88+legend_lines*16,max(48 if single else 96,y1-100))
            p.text(left+half/2,20,title,theme['ink'],(F,13,'bold'))
            data=[row for _,series in groups for row in series if row.get(metric) is not None and math.isfinite(row[metric])]
            if not data:
                p.text(left+half/2,h/2,'No matching data / Q undefined',theme['muted'],(F,11));continue
            xmin=min(r[axis] for r in data);xmax=max(r[axis] for r in data)
            ymin=min(r[metric]*scale for r in data);ymax=max(r[metric]*scale for r in data)
            yr=ymax-ymin
            if yr<=max(abs(ymin),abs(ymax))*1e-10:yr=max(abs(ymax)*.1,1e-6)
            ymin-=yr*.1;ymax+=yr*.1
            if metric in self.metric_minimums:ymin=max(ymin,self.metric_minimums[metric])
            if xmax==xmin:xmin-=.5;xmax+=.5
            def xy(row):return x0+(row[axis]-xmin)/(xmax-xmin)*(x1-x0),y1-(row[metric]*scale-ymin)/(ymax-ymin)*(y1-y0)
            for tick in range(5):
                y=y1-(y1-y0)*tick/4;x=x0+(x1-x0)*tick/4
                p.line([x0,y,x1,y],theme['grid'],1)
                p.text(x0-9,y,'{:.4g}'.format(ymin+(ymax-ymin)*tick/4),theme['muted'],(F,10),'e')
                p.text(x,y1+17,'{:.4g}'.format(xmin+(xmax-xmin)*tick/4),theme['muted'],(F,10))
            p.line([x0,y0,x0,y1,x1,y1],theme.get('axis',theme['ink']),1.2)
            xlabel=getattr(self,'axis_labels',{}).get(axis) or ('Frequency (GHz)' if axis=='frequency_GHz' else 'Scan point (index)' if axis=='point' else 'Decimal code' if axis=='code' else axis+' (decimal)')
            p.text((x0+x1)/2,h-17,xlabel,theme['ink'],(F,11))
            order=sorted(range(len(groups)),key=lambda i:groups[i][0]==self.selected)
            for index in order:
                label,series=groups[index];chosen=self.selected==label
                color=series_color(theme,index,len(groups))
                if self.selected and not chosen:color=mix(color,theme['bg'],.72)
                series=[r for r in series if r.get(metric) is not None and math.isfinite(r[metric])]
                points=[v for r in series for v in xy(r)]
                g=0 if (self.selected and not chosen) else glow*(2 if chosen else 1)
                if len(points)>=4:p.line(points,color,3.4 if chosen else 2,dash=None if index<len(theme['colors']) or theme.get('glow') else (6,3),glow=g)
                for row in series:
                    x,y=xy(row);radius=4.5 if chosen else 3.2
                    p.dot(x,y,radius,color,glow=g)
                    self.points.append(dict(curve=label,row=row,metric=metric,x=x,y=y,scale=scale,unit=unit,title=title))
                if index<4 and not single:
                    y=46+index*16
                    p.line([x0,y,x0+21,y],color,3.4 if chosen else 2,glow=g)
                    p.text(x0+28,y,label,color,(F,10,'bold' if chosen else 'normal'),'w')
                    tw,th=p.measure(label,(F,10))
                    self.legend_boxes.append((x0-2,y-8,x0+30+tw,y+8,label))
            if len(groups)>4:p.text(x1,46,'{} curves - use Slice'.format(len(groups)),theme['muted'],(F,10),'e')
        p.flush()
        self.curve_labels=keys

    def select_at(self,event):
        label=next((b[4] for b in self.legend_boxes if b[0]<=event.x<=b[2] and b[1]<=event.y<=b[3]),None)
        if label is None and self.points:
            q=min(self.points,key=lambda q:(q['x']-event.x)**2+(q['y']-event.y)**2)
            if (q['x']-event.x)**2+(q['y']-event.y)**2<=12**2:label=q['curve']
        self.selected=None if label==self.selected else label;self.draw()

    def clear_tooltip(self):
        self.delete('tooltip');self.tooltip_text=''

    def hover(self,event):
        self.clear_tooltip()
        points=[q for q in self.points if not self.selected or q['curve']==self.selected]
        if not points:return
        q=min(points,key=lambda q:(q['x']-event.x)**2+(q['y']-event.y)**2)
        if (q['x']-event.x)**2+(q['y']-event.y)**2>14**2:return
        row=q['row'];names='  '.join('{}={}'.format(n,row[n]) for n in self.names if n in row)
        value=row[q['metric']]*q['scale'];unit=q['unit'];metric=('C' if q['metric']=='C_F' else 'Q') if self.metrics is None else q['title']
        where='f = {:.9g} GHz   '.format(row['frequency_Hz']/1e9) if row.get('frequency_Hz') is not None else ''
        xname=getattr(self,'axis_labels',{}).get(self.axis) or self.axis
        xval=row.get(self.axis)
        xpart='{} = {:.6g}   '.format(xname,xval) if isinstance(xval,(int,float)) and self.axis!='frequency_GHz' else ''
        self.tooltip_text='{}\n{}{}{} = {:.9g} {}\n{}'.format(q['curve'],where,xpart,metric,value,unit,names)
        tooltip(self,THEMES[self.theme],self.FONT,q['x'],q['y'],self.tooltip_text)


def tooltip(canvas,theme,font,x,y,text):
    """Readout box next to a highlighted point (plain canvas items, above the plot image)."""
    tid=canvas.create_text(0,0,text=text,anchor='nw',fill=theme['ink'],font=(font,10),
                           width=max(80,min(430,canvas.winfo_width()-30)),tags=('tooltip',))
    b=canvas.bbox(tid);tw,th=b[2]-b[0],b[3]-b[1]
    tx=max(8,min(x+17,canvas.winfo_width()-tw-10));ty=max(8,min(y-th-16,canvas.winfo_height()-th-10))
    canvas.coords(tid,tx,ty);b=canvas.bbox(tid)
    rect=canvas.create_rectangle(b[0]-7,b[1]-5,b[2]+7,b[3]+5,fill=theme['box'],outline=theme.get('axis',theme['ink']),tags=('tooltip',))
    canvas.tag_raise(tid,rect)
    canvas.create_oval(x-7,y-7,x+7,y+7,outline=theme['ink'],width=2,tags=('tooltip',))
