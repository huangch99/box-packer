import streamlit as st
import plotly.graph_objects as go
import numpy as np

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Box Fit Visualizer", layout="wide")

st.title("📦 Shipping Box Fit Calculator")
st.markdown("""
**Expert Logic:** This tool calculates if an item fits in a box by automatically attempting 
to rotate the item along all 3 axes (Length, Width, Height) to find the best fit.
""")

# --- SIDEBAR INPUTS ---
st.sidebar.header("1. Box Dimensions (Inner)")
box_l = st.sidebar.number_input("Box Length", min_value=0.1, value=12.0)
box_w = st.sidebar.number_input("Box Width", min_value=0.1, value=8.0)
box_h = st.sidebar.number_input("Box Height", min_value=0.1, value=6.0)

st.sidebar.header("2. Item Dimensions")
item_l = st.sidebar.number_input("Item Length", min_value=0.1, value=10.0)
item_w = st.sidebar.number_input("Item Width", min_value=0.1, value=5.0)
item_h = st.sidebar.number_input("Item Height", min_value=0.1, value=4.0)

st.sidebar.header("3. Packing Configuration")
padding = st.sidebar.number_input("Padding/Tolerance (per side)", min_value=0.0, value=0.0, help="Space reserved for bubble wrap or peanuts")

# --- LOGIC FUNCTIONS ---

def check_fit(box_dims, item_dims, pad):
    """
    Sorts dimensions to account for rotation.
    Checks if Item dimensions + padding <= Box dimensions.
    """
    # Sort dimensions (Smallest to Largest) to simulate best rotation
    sorted_box = sorted(box_dims)
    sorted_item = sorted(item_dims)
    
    # Check if every dimension of the item fits within the box
    fits = True
    details = []
    
    for i, (b, it) in enumerate(zip(sorted_box, sorted_item)):
        needed = it + (pad * 2) # Padding on both sides
        if needed > b:
            fits = False
            details.append(f"Dimension mismatch: Item needs {needed:.2f} but Box is {b:.2f}")
            
    return fits, sorted_box, sorted_item, details

def get_cube_mesh(l, w, h, opacity=0.2, color='blue', name='Box'):
    x, y, z = l/2, w/2, h/2
    
    # 8 vertices of a cube centered at 0,0,0
    x_pts = [-x, -x, x, x, -x, -x, x, x]
    y_pts = [-y, y, y, -y, -y, y, y, -y]
    z_pts = [-z, -z, -z, -z, z, z, z, z]
    
    return go.Mesh3d(
        x=x_pts, y=y_pts, z=z_pts,
        i=[7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2],
        j=[3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3],
        k=[0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6],
        opacity=opacity,
        color=color,
        name=name,
        showscale=False
    )

def get_wireframe(l, w, h, color='black'):
    x, y, z = l/2, w/2, h/2
    # Define lines for the 12 edges of the box
    x_lines = [-x, -x, x, x, -x, -x, x, x, -x, -x, x, x, -x, x, x, -x]
    y_lines = [-y, y, y, -y, -y, y, y, -y, -y, -y, -y, -y, y, y, y, y]
    z_lines = [-z, -z, -z, -z, z, z, z, z, -z, z, z, -z, -z, z, z, -z]
    
    # Manually constructing line segments (Plotly Scatter3d is easier for lines)
    # A simpler way is plotting lines between corners
    pts = [
        (-x, -y, -z), (x, -y, -z), (x, y, -z), (-x, y, -z), (-x, -y, -z), # Bottom square
        (-x, -y, z), (x, -y, z), (x, y, z), (-x, y, z), (-x, -y, z),      # Top square
        (-x, -y, z), (-x, -y, -z),                                        # Connect verticals
        (x, -y, z), (x, -y, -z),
        (x, y, z), (x, y, -z),
        (-x, y, z), (-x, y, -z)
    ]
    
    X, Y, Z = [], [], []
    for p in pts:
        X.append(p[0])
        Y.append(p[1])
        Z.append(p[2])
        
    return go.Scatter3d(x=X, y=Y, z=Z, mode='lines', line=dict(color=color, width=4), name='Frame')

# --- MAIN APP LOGIC ---

# 1. Run Calculation
box_dims_raw = [box_l, box_w, box_h]
item_dims_raw = [item_l, item_w, item_h]

fits, s_box, s_item, issues = check_fit(box_dims_raw, item_dims_raw, padding)

# 2. Display Status
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Result")
    if fits:
        st.success("✅ IT FITS!")
        st.metric("Volume Efficiency", f"{((s_item[0]*s_item[1]*s_item[2]) / (s_box[0]*s_box[1]*s_box[2]) * 100):.1f}%")
    else:
        st.error("❌ DOES NOT FIT")
        for issue in issues:
            st.write(f"- {issue}")

    st.markdown("---")
    st.write("**Optimized Dimensions used for Calculation:**")
    st.write(f"Box: {s_box[0]} x {s_box[1]} x {s_box[2]}")
    st.write(f"Item: {s_item[0]} x {s_item[1]} x {s_item[2]}")

# 3. 3D Visualization
with col2:
    layout = go.Layout(
        scene=dict(
            xaxis=dict(title='Length', range=[-max(s_box), max(s_box)]),
            yaxis=dict(title='Width', range=[-max(s_box), max(s_box)]),
            zaxis=dict(title='Height', range=[-max(s_box), max(s_box)]),
            aspectmode='data'
        ),
        margin=dict(l=0, r=0, b=0, t=0),
        height=500
    )
    
    fig = go.Figure(layout=layout)
    
    # Draw Box (Wireframe + Light Mesh) - Use Sorted Dims to show the fit visually
    fig.add_trace(get_cube_mesh(s_box[0], s_box[1], s_box[2], opacity=0.1, color='grey', name='Box Volume'))
    fig.add_trace(get_wireframe(s_box[0], s_box[1], s_box[2], color='black'))
    
    # Draw Item (Solid Mesh) - Center it
    item_color = '#00CC96' if fits else '#EF553B'
    fig.add_trace(get_cube_mesh(s_item[0], s_item[1], s_item[2], opacity=1.0, color=item_color, name='Item'))

    st.plotly_chart(fig, use_container_width=True)
