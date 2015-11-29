var margin = {top: 20, right: 20, bottom: 30, left: 40},
    width = 960 - margin.left - margin.right,
    height = 500 - margin.top - margin.bottom,
    svg, firstTime = true,
    prev_bounds = null;

var x = d3.scale.linear()
    .range([0, width]),
    x0;

var y = d3.scale.linear()
    .range([height, 0]),
    y0;

var color = d3.scale.category10();

var xAxis = d3.svg.axis()
    .scale(x)
    .orient("bottom");

var yAxis = d3.svg.axis()
    .scale(y)
    .orient("left");

var zoom = d3.behavior.zoom()
    .x(x)
    .y(y)
    .scaleExtent([1, 32])
    .on("zoom", scatterplot_zoomed);

const DEFAULT_SIGMA = 2;
const DEFAULT_FILTER = "default";

const MAX_PREV_IMAGES = 3;
var imageHistory = new History(MAX_PREV_IMAGES);

function scatterplot_update(data) {
    module_update(data);
    scatterplot_update_vis(data);
}

function add_dots(data, index) {
    var dots = d3.select("#zoomable")
        .selectAll(".dot")
        .data(data['data'], function(d, i) { return index[i]; });
    
    //enter
    dots.enter().append("circle")
        .attr("class", "dot")
        .attr("r", 3.5)
        .attr("cx", function(d) { return x(d[0]); })
        .attr("cy", function(d) { return y(d[1]); })
        .style("fill", "blue") //function(d) { return color(d.species); });
        .append("title")
        .text(function(d, i) { return index[i]; });

    //update
    dots
        .attr("cx", function(d) { return x(d[0]); })
        .attr("cy", function(d) { return y(d[1]); });    
    //remove
    dots.exit().remove();
    //order
    dots.order();
}

function scatterplot_update_vis(rawdata) {
    var data = rawdata['scatterplot'],
        bounds = rawdata['bounds'],
        ix, iy, iw, ih;

    if (!data || !bounds) return;
    var index = data['index'], dots;

    if (firstTime) {
        prev_bounds = bounds;
        x.domain([bounds['xmin'], bounds['xmax']]).nice();
        y.domain([bounds['ymin'], bounds['ymax']]).nice();
        x0 = x.copy();
        y0 = y.copy();

        svg.append("rect")
            .attr("x", 0)
            .attr("y", 0)
            .attr("width", width)
            .attr("height", height)
            .attr("fill", "black");

        var zoomable = svg.append("g").attr('id', 'zoomable');

        ix = x(bounds['xmin']),
        iy = y(bounds['ymax']),
        iw = x(bounds['xmax'])-ix,
        ih = y(bounds['ymin'])-iy;
            
        zoomable.append("image")
            .attr("class", "heatmap")
            .attr("xlink:href", rawdata['image'])
            .attr("preserveAspectRatio", "none")
            .attr("x", ix)
            .attr("y", iy)
            .attr("width",  iw)
            .attr("height", ih)
            .attr("filter", "url(#gaussianBlur)");

        svg.append("image")
           .attr("class", "heatmapCompare")
           .attr("preserveAspectRatio", "none")
           .attr("opacity", 0.5)
            .attr("x", ix)
            .attr("y", iy)
            .attr("width",  iw)
            .attr("height", ih);

        svg.append("g")
            .attr("class", "x axis")
            .attr("transform", "translate(0," + height + ")")
            .call(xAxis)
            .append("text")
            .attr("class", "label")
            .attr("x", width)
            .attr("y", -6)
            .style("text-anchor", "end")
            .text([0]);

        svg.append("g")
            .attr("class", "y axis")
            .call(yAxis)
            .append("text")
            .attr("class", "label")
            .attr("transform", "rotate(-90)")
            .attr("y", 6)
            .attr("dy", ".71em")
            .style("text-anchor", "end")
            .text(data['columns'][1]);

        add_dots(data, index);
        firstTime = false;
    }
    else { // not firstTime
        var bounds_equal = true, //_.eq(bounds, prev_bounds),
            translate = zoom.translate(),
            scale = zoom.scale();

        if (! bounds_equal) {
            console.log('Bounds changed');
        }
        x0.domain([bounds['xmin'], bounds['xmax']]).nice();
        y0.domain([bounds['ymin'], bounds['ymax']]).nice();
        x.domain(x0.domain());
        y.domain(y0.domain());
        prev_bounds = bounds;

        ix = x(bounds['xmin']);
        iy = y(bounds['ymax']);
        iw = x(bounds['xmax'])-ix;
        ih = y(bounds['ymin'])-iy;
            
        svg.select(".heatmap")
            .attr("x", ix)
            .attr("y", iy)
            .attr("width",  iw)
            .attr("height", ih)
            .attr("xlink:href", rawdata['image']);

        svg.select(".heatmapCompare")
            .attr("x", ix)
            .attr("y", iy)
            .attr("width",  iw)
            .attr("height", ih);

        add_dots(data, index);

        zoom.x(x);
        zoom.y(y);
        zoom.scale(scale);
        zoom.translate(translate);
        x.domain(x0.range().map(function(x) { return (x - translate[0]) / scale; }).map(x0.invert));
        y.domain(y0.range().map(function(y) { return (y - translate[1]) / scale; }).map(y0.invert));
        zoom.event(svg);
    }
    var imgSrc = rawdata['image'];
    imageHistory.enqueueUnique(imgSrc);

    var prevImgElements = d3.select("#prevImages").selectAll("img")
      .data(imageHistory.getItems(), function(d){ return d; }); 

    prevImgElements.enter()
    .append("img")
    .attr("width", 50)
    .attr("height", 50)
    .on("mouseover", function(d){
      d3.select(".heatmapCompare")
        .attr("xlink:href", d)
        .attr("visibility", "inherit");
    })
    .on("mouseout", function(d){
      d3.select(".heatmapCompare")
        .attr("visibility", "hidden");
    });

    prevImgElements.transition().duration(500)
        .attr("src", function(d){ return d; })
        .attr("width", 100)
        .attr("height", 100);

    prevImgElements.exit().transition().duration(500)
        .attr("width", 5)
        .attr("height", 5)
        .remove();
}

function scatterplot_zoomed() {
    svg.select(".x.axis").call(xAxis);
    svg.select(".y.axis").call(yAxis);
    svg.select("#zoomable")
        .attr("transform", "translate(" + d3.event.translate + ")scale(" + d3.event.scale + ")");
    svg.selectAll(".dot").attr("r", 3.5/d3.event.scale);
}


function scatterplot_refresh() {
  module_get(scatterplot_update, error);
}


/**
 * @param select - a select element that will be mutated 
 * @param names - list of option names (the value of an option is set to its name)
 */
function makeOptions(select, names){
  if(!select){
    console.warn("makeOptions requires an existing select element");
    return;
  }
  names.forEach(function(name){
    var option = document.createElement("option");
    option.setAttribute("value", name);
    option.innerHTML = name;
    select.appendChild(option);
  });
}

function ignore(data) {}

function scatterplot_filter() {
    var xmin    = x.invert(0),
        xmax    = x.invert(width),
        ymin    = y.invert(height),
        ymax    = y.invert(0),
        bounds  = progressivis_data['bounds'],
        columns = progressivis_data['columns'],
        min     = {},
        max     = {};


    if (xmin > bounds['xmin'])
        min[columns[0]] = xmin;
    else
        min[columns[0]] = null; // NaN means bump to min
    if (xmax < bounds['xmax']) 
        max[columns[0]] = xmax;
    else
        max[columns[0]] = null;

    if (ymin > bounds['ymin'])
        min[columns[1]] = ymin;
    else
        min[columns[1]] = null;

    if (ymax < bounds['ymax'])
        max[columns[1]] = ymax;
    else
        max[columns[1]] = null;
    
    module_input(min, ignore, progressivis_error, module_id+"/range_query/min_value");
    module_input(max, ignore, progressivis_error, module_id+"/range_query/max_value");
}

function scatterplot_ready() {
    svg = d3.select("#scatterplot svg")
         .attr("width", width + margin.left + margin.right)
         .attr("height", height + margin.top + margin.bottom)
        .append("g")
         .attr("transform", "translate(" + margin.left + "," + margin.top + ")")
         .call(zoom);

    $('#nav-tabs a').click(function (e) {
        e.preventDefault();
        $(this).tab('show');
    });

    const gaussianBlur = document.getElementById("gaussianBlurElement");
    const filterSlider = $("#filterSlider");
    filterSlider.change(function(){
      gaussianBlur.setStdDeviation(this.value, this.value);
    });
    filterSlider.get(0).value = DEFAULT_SIGMA;
    gaussianBlur.setStdDeviation(DEFAULT_SIGMA, DEFAULT_SIGMA);

    const colorMap = document.getElementById("colorMap");
    const colorMapSelect = $("#colorMapSelect");
    colorMapSelect.change(function(){
      colormaps.makeTableFilter(colorMap, this.value);
    });
    colorMapSelect.get(0).value = DEFAULT_FILTER;
    makeOptions(colorMapSelect.get(0), colormaps.getTableNames());

    $('#filter').click(function() { scatterplot_filter(); });
    
    refresh = scatterplot_refresh; // function to call to refresh
    module_ready();
}
