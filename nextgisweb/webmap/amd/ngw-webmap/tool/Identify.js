/*global console, OpenLayers*/
define([
    "dojo/_base/declare",
    "./Base",
    "dojo/_base/lang",
    "dojo/_base/array",
    "dojo/Deferred",
    "dojo/promise/all",
    "dojo/json",
    "dojo/request/xhr",
    "dojo/dom-class",
    "dojo/dom-style",
    "dojo/dom-construct",
    "dojo/on",
    "dojo/topic",
    "dijit/layout/BorderContainer",
    "dijit/layout/ContentPane",
    "dijit/layout/StackContainer",
    "dijit/layout/StackController",
    "dijit/form/Select",
    "dijit/form/Button",
    "put-selector/put",
    "ngw/route",
    "openlayers/ol",
    "ngw/openlayers/Popup",
    "ngw-pyramid/i18n!webmap",
    "ngw-feature-layer/FieldsDisplayWidget",
    "ngw-feature-layer/FeatureEditorWidget",
    // settings
    "ngw/settings!feature_layer",
    "ngw/settings!webmap",
    // css
    "xstyle/css!./resources/Identify.css"
], function (
    declare,
    Base,
    lang,
    array,
    Deferred,
    all,
    json,
    xhr,
    domClass,
    domStyle,
    domConstruct,
    on,
    topic,
    BorderContainer,
    ContentPane,
    StackContainer,
    StackController,
    Select,
    Button,
    put,
    route,
    ol,
    Popup,
    i18n,
    FieldsDisplayWidget,
    FeatureEditorWidget,
    featureLayersettings,
    webmapSettings
) {

    var Control = function(options) {
        this.tool = options.tool;
        ol.interaction.Interaction.call(this, {
            handleEvent: Control.prototype.handleClickEvent
        });
    };
    ol.inherits(Control, ol.interaction.Interaction);

    Control.prototype.handleClickEvent = function(evt) {
        if (evt.type == 'singleclick') {
            this.tool.execute(evt.pixel);
            evt.preventDefault();
        }
        return true;
    };

    var Widget = declare([BorderContainer], {
        style: "width: 100%; height: 100%",
        gutters: false,

        postCreate: function () {
            this.inherited(arguments);

            this.selectOptions = [];

            var layersResponse = Object.keys(this.response);
            this.tool.display.itemStore.fetch({
                scope: this,
                queryOptions: {deep: true},
                query: {type: "layer"},
                onItem: function (item) {
                    var itemObj = this.tool.display.itemStore.dumpItem(item),
                        layerId = itemObj.layerId.toString(),
                        layerIdx = layersResponse.indexOf(layerId);

                    if (layerIdx > -1) {
                        var layerResponse = this.response[layerId];
                        var idx = 0;
                        array.forEach(layerResponse.features, function (feature) {
                            var label = put("div[style=\"overflow: hidden; display: inline-block; text-align: left;\"] $ span[style=\"color: gray\"] $ <", feature.label, " (" + this.layerLabels[layerId] + ")");
                            domStyle.set(label, "width", (this.popupSize[0] - 35) + "px");
                            this.selectOptions.push({
                                label: label.outerHTML,
                                value: layerId + "/" + idx
                            });
                            idx++;
                        }, this);
                        layersResponse.splice(layerIdx, 1);
                    }
                }
            });

            this.selectPane = new ContentPane({
                region: "top", layoutPriority: 1,
                style: "padding: 0 2px 0 1px"
            });

            this.addChild(this.selectPane);

            this.select = new Select({
                style: "width: 100%",
                options: this.selectOptions
            }).placeAt(this.selectPane);

            // create widgets for all extensions of IFeatureLayer
            var deferreds = [];
            var widget = this;

            widget.extWidgetClasses = {};

            array.forEach(Object.keys(featureLayersettings.extensions), function (key) {
                var ext = featureLayersettings.extensions[key];

                var deferred = new Deferred();
                deferreds.push(deferred);

                require([ext], function (cls) {
                    widget.extWidgetClasses[key] = cls;
                    deferred.resolve(widget);
                });
            }, this);

            this.extWidgetClassesDeferred = all(deferreds);
        },

        startup: function () {
            this.inherited(arguments);

            var widget = this;

            this.select.watch("value", function (attr, oldVal, newVal) {
                widget._displayFeature(widget._featureResponse(newVal));
            });
            this._displayFeature(this._featureResponse(this.select.get("value")));
        },

        _featureResponse: function (selectValue) {
            var keys = selectValue.split("/");
            return this.response[keys[0]].features[keys[1]];
        },

        _displayFeature: function (feature) {
            var widget = this, lid = feature.layerId, fid = feature.id;

            var iurl = route.feature_layer.feature.item({id: lid, fid: fid});

            xhr.get(iurl, {
                method: "GET",
                handleAs: "json"
            }).then(function (feature) {
                widget.extWidgetClassesDeferred.then(function () {
                    if (widget.featureContainer) {
                        widget.featureContainer.destroyRecursive();
                    }

                    widget.featureContainer = new BorderContainer({region: "center", gutters: false});
                    widget.addChild(widget.featureContainer);

                    widget.extContainer = new StackContainer({
                        region: "center", style: "overflow-y: scroll"});

                    widget.featureContainer.addChild(widget.extContainer);

                    widget.extController = new StackController({
                        region: "top", layoutPriority: 2,
                        containerId: widget.extContainer.id
                    });
                    domClass.add(widget.extController.domNode, "ngwWebmapToolIdentify-controller");

                    widget.featureContainer.addChild(widget.extController);

                    // Show attributes widget only if it is not turned off
                    // in settings
                    if (featureLayersettings.identify.attributes) {
                        var fwidget = new FieldsDisplayWidget({
                            resourceId: lid, featureId: fid,
                            compact: true, title: i18n.gettext("Attributes")});

                        fwidget.renderValue(feature.fields);
                        fwidget.placeAt(widget.extContainer);
                    }

                    array.forEach(Object.keys(widget.extWidgetClasses), function (key) {
                        var cls = widget.extWidgetClasses[key],
                            ewidget = new cls({
                                resourceId: lid, featureId: fid,
                                compact: true});

                        ewidget.renderValue(feature.extensions[key]);
                        ewidget.placeAt(widget.extContainer);
                    });

                    widget.editButton = new Button({
                        iconClass: "dijitIconEdit",
                        showLabel: true,
                        onClick: function () {
                            xhr(route.resource.item({id: lid}), {
                                method: "GET",
                                handleAs: "json"
                            }).then(function (data) {
                                var fieldmap = {};
                                array.forEach(data.feature_layer.fields, function (itm) {
                                    fieldmap[itm.keyname] = itm;
                                });
                                
                                var pane = new FeatureEditorWidget({
                                    resource: lid, feature: fid,
                                    fields: data.feature_layer.fields, 
                                    title: i18n.gettext("Feature") + " #" + fid,
                                    iconClass: "iconDescription",
                                    closable: true
                                });

                                widget.tool.display.tabContainer.addChild(pane);
                                widget.tool.display.tabContainer.selectChild(pane);

                                pane.startup();
                                pane.load();
                            });
                        }
                    }).placeAt(widget.extController, "last");
                    domClass.add(widget.editButton.domNode, "no-label");

                    widget.resize();

                });

                topic.publish("feature.highlight", {geom: feature.geom});
            });
        }
    });

    return declare(Base, {
        label: i18n.gettext("Identify"),
        iconClass: "iconIdentify",

        // Seach features radius in pixels
        pixelRadius: webmapSettings.identify_radius,

        // popup width
        popupWidth: webmapSettings.popup_width,

        // popup height
        popupHeight: webmapSettings.popup_height,


        constructor: function () {
            this.map = this.display.map;
            this.control = new Control({tool: this});
            this.control.setActive(false);
            this.display.map.olMap.addInteraction(this.control);

            this._bindEvents();

            this._popup = new Popup({
                title: i18n.gettext("Identify"),
                size: [this.popupWidth, this.popupHeight]
            });
            this.display.map.olMap.addOverlay(this._popup);
        },

        _bindEvents: function () {
            topic.subscribe('webmap/tool/identify/on', lang.hitch(this, function () {
                this.activate();
            }));

            topic.subscribe('webmap/tool/identify/off', lang.hitch(this, function () {
                this.deactivate();
            }));
        },

        activate: function () {
            this.control.setActive(true);
        },

        deactivate: function () {
            this.control.setActive(false);
            this._popup.setPosition(undefined);
        },

        execute: function (pixel) {
            var tool = this,
                olMap = this.display.map.olMap,
                point = olMap.getCoordinateFromPixel(pixel);

            var request = {
                srs: 3857,
                geom: this._requestGeomString(pixel),
                layers: []
            };

            this.display.getVisibleItems().then(function (items) {
                if (items.length === 0) {
                    // No visible items currently
                    console.log("Visible items not found!");
                } else {
                    // Add list of visible items to a request,
                    // taking scale visibility into cosideration
                    var mapResolution = this.display.map.get("resolution");
                    array.forEach(items, function (i) {
                        var item = this.display._itemConfigById[
                            this.display.itemStore.getValue(i, "id")];
                        if (mapResolution >= item.maxResolution ||
                            mapResolution < item.minResolution) {
                            return;
                        }
                        request.layers.push(item.layerId);
                    }, this);

                    var layerLabels = {};
                    array.forEach(items, function (i) {
                        layerLabels[this.display.itemStore.getValue(i, "layerId")] = this.display.itemStore.getValue(i, "label");
                    }, this);

                    // XHR-request to service
                    xhr.post(route.feature_layer.identify(), {
                        handleAs: "json",
                        data: json.stringify(request),
                        headers: {
                            'Content-Type': 'application/json'
                        }
                    }).then(function (response) {
                        tool._responsePopup(response, point, layerLabels);
                    });
                }
            });

        },

        // WKT-string for search features geometry for point pixel
        _requestGeomString: function (pixel) {
            var olMap = this.map.olMap,
                bounds;

            bounds = ol.extent.boundingExtent([
                olMap.getCoordinateFromPixel([
                    pixel[0] - this.pixelRadius,
                    pixel[1] - this.pixelRadius
                ]),
                olMap.getCoordinateFromPixel([
                    pixel[0] + this.pixelRadius,
                    pixel[1] + this.pixelRadius
                ])
            ]);

            return new ol.format.WKT().writeGeometry(
                ol.geom.Polygon.fromExtent(bounds));
        },

        _responsePopup: function (response, point, layerLabels) {
            if (response.featureCount === 0) {
                this._popup.setPosition(undefined);
                topic.publish("feature.unhighlight");
                return;
            }

            domConstruct.empty(this._popup.contentDiv);

            var widget = new Widget({
                response: response,
                tool: this,
                layerLabels: layerLabels,
                popupSize: [this.popupWidth, this.popupHeight]
            });
            this._popup.widget = widget;

            widget.placeAt(this._popup.contentDiv);

            this._popup.setTitle(i18n.gettext("Features") + ": " + response.featureCount);
            this._popup.setPosition(point);

            // Closing function
            on(this._popup._closeSpan, "click", lang.hitch(this, function () {
                this._popup.setPosition(undefined);
                topic.publish("feature.unhighlight");
            }));
        }

    });
});
