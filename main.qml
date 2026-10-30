pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Dialogs
import QtQuick.Layouts

ApplicationWindow {
    id: window
    width: 1240
    height: 900
    minimumWidth: 760
    minimumHeight: 640
    visible: true
    title: qsTr("Boolean Logic Workbench")
    color: "#f3f6f8"
    Material.theme: Material.Light
    Material.accent: "#0f766e"

    readonly property color ink: "#172b3a"
    readonly property color muted: "#6b7c88"
    readonly property color accent: "#0f766e"
    readonly property color accentSoft: "#e5f4f1"
    readonly property color border: "#e1e9e9"
    readonly property color surface: "#ffffff"
    property var positions: ({})
    property var backend: logic
    property string connectionSource: ""
    property bool wireMode: false
    property real schemeZoom: 1.0

    function fitScheme() {
        var availableWidth = diagramScroll.availableWidth - 32
        var availableHeight = diagramScroll.availableHeight - 32
        if (availableWidth <= 0 || availableHeight <= 0)
            return
        schemeZoom = Math.max(0.08, Math.min(
            1.0,
            availableWidth / backend.schemeWidth,
            availableHeight / backend.schemeHeight
        ))
    }

    function loadCanonicalForm(mode) {
        tabs.currentIndex = 0
        inputMode.currentIndex = mode === "SOP" ? 0 : 1
        expressionInput.text = mode === "SOP" ? backend.sop : backend.pos
        expressionInput.forceActiveFocus()
        expressionInput.cursorPosition = expressionInput.length
    }

    function syncActiveOutput() {
        inputMode.currentIndex = backend.activeMode === "POS" ? 1 : 0
        expressionInput.text = backend.activeSource
    }

    function refreshPositions() {
        var current = ({})
        for (var i = 0; i < backend.schemeNodes.length; i++) {
            var node = backend.schemeNodes[i]
            current[node.id] = {
                x: node.x, y: node.y, width: node.width, height: node.height
            }
        }
        positions = current
        if (typeof wireCanvas !== "undefined")
            wireCanvas.requestPaint()
    }

    function updatePosition(nodeId, x, y) {
        var node = positions[nodeId]
        if (!node)
            return
        var next = Object.assign({}, positions)
        next[nodeId] = {
            x: Math.max(0, Math.min(x, backend.schemeWidth - node.width)),
            y: Math.max(0, Math.min(y, backend.schemeHeight - node.height)),
            width: node.width,
            height: node.height
        }
        positions = next
        wireCanvas.requestPaint()
    }

    Component.onCompleted: refreshPositions()

    header: ColumnLayout {
        spacing: 0
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 82
            color: "#102a3a"
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 26
                anchors.rightMargin: 26
                spacing: 14
                Rectangle {
                    Layout.preferredWidth: 44
                    Layout.preferredHeight: 44
                    radius: 13
                    color: "#14a895"
                    Label {
                        anchors.centerIn: parent
                        text: "B"
                        color: "#ffffff"
                        font.pixelSize: 24
                        font.bold: true
                    }
                }
                ColumnLayout {
                    spacing: 3
                    Label {
                        text: qsTr("Boolean Logic Workbench")
                        font.pixelSize: 21
                        font.bold: true
                        color: "#f4fbfa"
                    }
                    Label {
                        text: qsTr("Explore · simplify · design")
                        font.pixelSize: 12
                        color: "#b7cacd"
                    }
                }
                Item { Layout.fillWidth: true }
                Label {
                    text: qsTr("%1 VARIABLES").arg(window.backend.variableCount)
                    color: "#c8e9e3"
                    font.pixelSize: 10
                    font.bold: true
                    padding: 9
                    background: Rectangle {
                        color: "#214454"
                        radius: 12
                    }
                }
                Button {
                    text: qsTr("Export PDF")
                    enabled: window.backend.hasScheme
                    contentItem: Label {
                        text: qsTr("Export PDF")
                        color: "#ffffff"
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        radius: 10
                        color: parent.enabled ? "#14a895" : "#37515c"
                    }
                    onClicked: pdfDialog.open()
                }
            }
        }
        TabBar {
            id: tabs
            objectName: "mainTabs"
            Layout.fillWidth: true
            Layout.preferredHeight: 62
            spacing: 8
            leftPadding: 20
            rightPadding: 20
            background: Rectangle {
                color: "#eaf0f1"
                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: 1
                    color: "#dce5e6"
                }
            }
            onCurrentIndexChanged: {
                if (currentIndex === 2)
                    Qt.callLater(window.fitScheme)
            }
            TabButton {
                id: formsTab
                text: qsTr("Build function")
                implicitWidth: 174
                implicitHeight: 44
                contentItem: Label {
                    text: formsTab.text
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.pixelSize: 13
                    font.weight: formsTab.checked ? Font.DemiBold : Font.Medium
                    color: formsTab.checked ? window.accent : window.muted
                }
                background: Rectangle {
                    radius: 10
                    color: formsTab.checked ? "#ffffff" : "transparent"
                    border.color: formsTab.checked ? "#d9e7e5" : "transparent"
                }
            }
            TabButton {
                id: tableTab
                text: qsTr("Truth table")
                implicitWidth: 150
                implicitHeight: 44
                contentItem: Label {
                    text: tableTab.text
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.pixelSize: 13
                    font.weight: tableTab.checked ? Font.DemiBold : Font.Medium
                    color: tableTab.checked ? window.accent : window.muted
                }
                background: Rectangle {
                    radius: 10
                    color: tableTab.checked ? "#ffffff" : "transparent"
                    border.color: tableTab.checked ? "#d9e7e5" : "transparent"
                }
            }
            TabButton {
                id: schemeTab
                text: qsTr("Gate scheme")
                implicitWidth: 150
                implicitHeight: 44
                contentItem: Label {
                    text: schemeTab.text
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.pixelSize: 13
                    font.weight: schemeTab.checked ? Font.DemiBold : Font.Medium
                    color: schemeTab.checked ? window.accent : window.muted
                }
                background: Rectangle {
                    radius: 10
                    color: schemeTab.checked ? "#ffffff" : "transparent"
                    border.color: schemeTab.checked ? "#d9e7e5" : "transparent"
                }
            }
        }
    }

    StackLayout {
        anchors.fill: parent
        anchors.topMargin: 0
        currentIndex: tabs.currentIndex

        ScrollView {
            id: formsScroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AsNeeded
            ColumnLayout {
                x: 22
                y: 20
                width: Math.max(formsScroll.availableWidth - 44, 620)
                spacing: 18
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 380
                    radius: 16
                    color: window.surface
                    border.color: window.border
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 22
                        spacing: 12
                        RowLayout {
                            Layout.fillWidth: true
                            ColumnLayout {
                                spacing: 3
                                Label {
                                    text: qsTr("Build a Boolean function")
                                    font.pixelSize: 19
                                    font.bold: true
                                    color: window.ink
                                }
                                Label {
                                    text: qsTr("Enter a canonical form to generate the table and gate scheme.")
                                    font.pixelSize: 12
                                    color: window.muted
                                }
                            }
                            Item { Layout.fillWidth: true }
                            Label {
                                text: qsTr("INPUT")
                                color: window.accent
                                font.pixelSize: 10
                                font.bold: true
                                padding: 8
                                background: Rectangle {
                                    color: window.accentSoft
                                    radius: 9
                                }
                            }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            Label {
                                text: qsTr("Form")
                                color: window.ink
                                font.bold: true
                            }
                            ComboBox {
                                id: inputMode
                                model: [
                                    qsTr("Disjunctive (SOP)"),
                                    qsTr("Conjunctive (POS)")
                                ]
                                Layout.preferredWidth: 245
                            }
                            Item { Layout.fillWidth: true }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            Label {
                                text: qsTr("Output")
                                color: window.ink
                                font.bold: true
                            }
                            ComboBox {
                                id: outputSelector
                                objectName: "outputSelector"
                                model: window.backend.outputOptions
                                textRole: "name"
                                valueRole: "id"
                                currentIndex: {
                                    for (var index = 0; index < model.length; index++) {
                                        if (model[index].id === window.backend.activeOutputId)
                                            return index
                                    }
                                    return 0
                                }
                                Layout.preferredWidth: 150
                                onActivated: {
                                    window.backend.selectOutput(currentValue)
                                    window.syncActiveOutput()
                                }
                            }
                            TextField {
                                id: newOutputName
                                Layout.preferredWidth: 140
                                placeholderText: qsTr("New output name")
                                color: window.ink
                                placeholderTextColor: window.muted
                                onAccepted: {
                                    window.backend.addOutput(text)
                                    clear()
                                    window.syncActiveOutput()
                                }
                            }
                            Button {
                                text: qsTr("Add output")
                                onClicked: {
                                    window.backend.addOutput(newOutputName.text)
                                    newOutputName.clear()
                                    window.syncActiveOutput()
                                }
                            }
                            Button {
                                text: qsTr("Remove")
                                enabled: window.backend.outputOptions.length > 1
                                onClicked: {
                                    window.backend.removeActiveOutput()
                                    window.syncActiveOutput()
                                }
                            }
                            Item { Layout.fillWidth: true }
                        }
                        TextArea {
                            id: expressionInput
                            objectName: "expressionInput"
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Layout.minimumHeight: 90
                            placeholderText: ""
                            wrapMode: TextEdit.Wrap
                            selectByMouse: true
                            leftPadding: 12
                            rightPadding: 12
                            topPadding: 12
                            bottomPadding: 10
                            font.family: "monospace"
                            font.pixelSize: 14
                            color: "#17233b"
                            placeholderTextColor: "#75839a"
                            selectionColor: "#b8cff4"
                            selectedTextColor: window.ink
                            background: Rectangle {
                                color: "#f7fafb"
                                border.color: expressionInput.activeFocus
                                    ? window.accent : "#dce6e6"
                                radius: 10
                                Text {
                                    anchors.fill: parent
                                    anchors.leftMargin: 12
                                    anchors.topMargin: 10
                                    text: inputMode.currentIndex === 0
                                        ? "Example: A'B'C'D'E' + ABCDE"
                                        : "Example: ΠP(1, 2, 3)"
                                    color: "#84949d"
                                    font: expressionInput.font
                                    wrapMode: Text.Wrap
                                    verticalAlignment: Text.AlignTop
                                    visible: expressionInput.text.length === 0
                                }
                            }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            Button {
                                text: qsTr("Generate results")
                                highlighted: true
                                onClicked: window.backend.calculate(
                                    inputMode.currentIndex === 0 ? "SOP" : "POS",
                                    expressionInput.text
                                )
                            }
                            Label {
                                Layout.fillWidth: true
                                text: window.backend.error
                                    || (window.backend.hasResult
                                        ? qsTr("Function calculated. See the results above.")
                                        : qsTr("Ready when you are."))
                                color: window.backend.error
                                    ? (window.backend.error.startsWith("PDF exported")
                                        ? "#21824a" : "#bd3b3b")
                                    : window.muted
                                wrapMode: Text.Wrap
                            }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Label {
                        text: qsTr("Generated forms · %1").arg(window.backend.activeOutputName)
                        font.pixelSize: 17
                        font.bold: true
                        color: window.ink
                    }
                    Item { Layout.fillWidth: true }
                    Label {
                        text: qsTr("OUTPUT")
                        color: window.muted
                        font.pixelSize: 10
                        font.bold: true
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 14
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 260
                        Layout.preferredHeight: 186
                        radius: 14
                        color: window.surface
                        border.color: window.border
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 16
                            spacing: 10
                            Label {
                                text: qsTr("Disjunctive form  ·  SOP")
                                font.bold: true
                                color: window.ink
                            }
                            TextArea {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                text: window.backend.hasResult ? window.backend.sop : ""
                                placeholderText: qsTr("Your SOP result will appear here")
                                readOnly: true
                                wrapMode: TextEdit.Wrap
                                selectByMouse: true
                                font.family: "monospace"
                                font.pixelSize: 13
                                color: window.ink
                                placeholderTextColor: "#9aa9ae"
                                selectedTextColor: window.ink
                                background: Rectangle {
                                    color: "#f7fafb"
                                    radius: 8
                                }
                            }
                            Button {
                                text: qsTr("Use as input")
                                Layout.alignment: Qt.AlignRight
                                enabled: window.backend.hasResult
                                onClicked: window.loadCanonicalForm("SOP")
                            }
                        }
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 260
                        Layout.preferredHeight: 186
                        radius: 14
                        color: window.surface
                        border.color: window.border
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 16
                            spacing: 10
                            Label {
                                text: qsTr("Conjunctive form  ·  POS")
                                font.bold: true
                                color: window.ink
                            }
                            TextArea {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                text: window.backend.hasResult ? window.backend.pos : ""
                                placeholderText: qsTr("Your POS result will appear here")
                                readOnly: true
                                wrapMode: TextEdit.Wrap
                                selectByMouse: true
                                font.family: "monospace"
                                font.pixelSize: 13
                                color: window.ink
                                placeholderTextColor: "#9aa9ae"
                                selectedTextColor: window.ink
                                background: Rectangle {
                                    color: "#f7fafb"
                                    radius: 8
                                }
                            }
                            Button {
                                text: qsTr("Use as input")
                                Layout.alignment: Qt.AlignRight
                                enabled: window.backend.hasResult
                                onClicked: window.loadCanonicalForm("POS")
                            }
                        }
                    }
                }
                Item { Layout.preferredHeight: 12 }
            }
        }

        ScrollView {
            id: tableScroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            ColumnLayout {
                x: 22
                y: 20
                width: Math.max(tableScroll.availableWidth - 44, 670)
                spacing: 18
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 110
                    radius: 16
                    color: window.surface
                    border.color: window.border
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 22
                        anchors.rightMargin: 22
                        anchors.topMargin: 15
                        anchors.bottomMargin: 15
                        RowLayout {
                            Layout.fillWidth: true
                            Label {
                                Layout.fillWidth: true
                                text: qsTr("Truth table · %1 variables")
                                    .arg(window.backend.variableCount)
                                font.pixelSize: 20
                                font.bold: true
                                color: window.ink
                            }
                            Label {
                                text: qsTr("%1 TABLES · %2 OUTPUTS")
                                    .arg(tableView.tableCards.length)
                                    .arg(window.backend.outputOptions.length)
                                color: window.accent
                                font.pixelSize: 10
                                font.bold: true
                                padding: 8
                                background: Rectangle {
                                    color: window.accentSoft
                                    radius: 9
                                }
                            }
                            Button {
                                text: qsTr("Clear values")
                                enabled: window.backend.hasResult
                                onClicked: window.backend.clearTable()
                            }
                        }
                        Label {
                            text: qsTr("Toggle a P cell to edit that output. Extra variables are fixed per 4×4 table; every output has its own tables.")
                            color: window.muted
                            wrapMode: Text.Wrap
                        }
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 14
                    Repeater {
                        model: tableView.tableCards
                        delegate: Rectangle {
                            required property var modelData
                            objectName: "tableCard_" + modelData.outputId
                                + "_" + modelData.sliceIndex
                            Layout.fillWidth: true
                            Layout.preferredHeight: 390
                            radius: 16
                            color: window.surface
                            border.color: window.border
                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 16
                                spacing: 8
                                Label {
                                    Layout.fillWidth: true
                                    text: modelData.outputName
                                        + (modelData.assignment
                                            ? "  ·  " + modelData.assignment : "")
                                    font.bold: true
                                    color: window.ink
                                }
                                Image {
                                    id: tableImage
                                    objectName: "tableImage_" + modelData.outputId
                                        + "_" + modelData.sliceIndex
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    cache: false
                                    fillMode: Image.Stretch
                                    source: modelData.imageUrl
                                    TapHandler {
                                        onTapped: function(eventPoint) {
                                            tableView.toggleCellAt(
                                                modelData.outputId,
                                                modelData.sliceIndex,
                                                eventPoint.position.x,
                                                eventPoint.position.y,
                                                tableImage.width,
                                                tableImage.height
                                            )
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 142
                color: window.surface
                ColumnLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 22
                    anchors.rightMargin: 22
                    anchors.topMargin: 14
                    anchors.bottomMargin: 12
                    spacing: 8
                    RowLayout {
                        Layout.fillWidth: true
                        Label {
                            Layout.fillWidth: true
                            text: qsTr("Circuit tools")
                            font.pixelSize: 17
                            font.bold: true
                            color: window.ink
                        }
                        ComboBox {
                            id: newGateType
                            model: ["AND", "OR", "NOT", "INPUT", "OUTPUT", "0", "1"]
                            Layout.preferredWidth: 112
                        }
                        TextField {
                            id: newGateLabel
                            Layout.preferredWidth: 150
                            placeholderText: qsTr("Optional label")
                            color: window.ink
                            placeholderTextColor: window.muted
                        }
                        Button {
                            text: qsTr("Add gate")
                            highlighted: true
                            onClicked: {
                                window.backend.addGate(newGateType.currentText, newGateLabel.text)
                                newGateLabel.clear()
                            }
                        }
                        Button {
                            text: window.wireMode ? qsTr("Cancel wire") : qsTr("Connect")
                            highlighted: window.wireMode
                            onClicked: {
                                window.wireMode = !window.wireMode
                                window.connectionSource = ""
                            }
                        }
                        Button {
                            text: qsTr("Undo")
                            enabled: window.backend.canUndoScheme
                            onClicked: window.backend.undoScheme()
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Label {
                            Layout.fillWidth: true
                            text: window.backend.error
                                ? window.backend.error
                                : window.backend.schemeKind === "MUX"
                                    ? qsTr("MUX synthesized from the current f · drag gates or add custom logic")
                                : window.backend.schemeKind === "FORMULA"
                                    ? window.backend.schemeDescription
                                : window.connectionSource
                                    ? qsTr("Choose destination for %1.").arg(window.connectionSource)
                                    : window.wireMode
                                        ? qsTr("Choose a source gate, then its destination.")
                                        : qsTr("Drag gates to move them; use Fit, zoom, and scrollbars to navigate.")
                            color: window.backend.error ? "#b3261e" : window.muted
                            elide: Text.ElideRight
                        }
                        Button {
                            text: qsTr("Synthesize f as 4:1 MUX")
                            enabled: window.backend.hasResult
                            ToolTip.visible: hovered && !enabled
                            ToolTip.text: qsTr("Enter a function in the Function tab first.")
                            onClicked: {
                                window.backend.generateMultiplexer()
                                window.fitScheme()
                            }
                        }
                        Button {
                            text: qsTr("Fit scheme")
                            onClicked: window.fitScheme()
                        }
                        Button {
                            text: "−"
                            onClicked: window.schemeZoom = Math.max(0.08, window.schemeZoom - 0.1)
                        }
                        Slider {
                            id: zoomSlider
                            from: 0.08
                            to: 1.5
                            stepSize: 0.05
                            value: window.schemeZoom
                            Layout.preferredWidth: 140
                            onMoved: window.schemeZoom = value
                        }
                        Label {
                            Layout.preferredWidth: 48
                            text: Math.round(window.schemeZoom * 100) + "%"
                            color: window.muted
                        }
                        Button {
                            text: "+"
                            onClicked: window.schemeZoom = Math.min(1.5, window.schemeZoom + 0.1)
                        }
                    }
                }
            }
            ScrollView {
                id: diagramScroll
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AsNeeded
                ScrollBar.vertical.policy: ScrollBar.AsNeeded
                Item {
                    id: diagramViewport
                    width: Math.ceil(window.backend.schemeWidth * window.schemeZoom)
                    height: Math.ceil(window.backend.schemeHeight * window.schemeZoom)
                    Rectangle {
                        anchors.fill: parent
                        color: "#f8fbfb"
                    }
                    Item {
                        id: diagram
                        width: window.backend.schemeWidth
                        height: window.backend.schemeHeight
                        scale: window.schemeZoom
                        transformOrigin: Item.TopLeft
                        Rectangle {
                            anchors.fill: parent
                            color: "#f8fbfb"
                            z: -1
                        }
                        Canvas {
                            anchors.fill: parent
                            z: 0
                            onPaint: {
                                var ctx = getContext("2d")
                                ctx.clearRect(0, 0, width, height)
                                ctx.fillStyle = "#dfe8e8"
                                for (var x = 20; x < width; x += 32) {
                                    for (var y = 20; y < height; y += 32) {
                                        ctx.beginPath()
                                        ctx.arc(x, y, 1, 0, 2 * Math.PI)
                                        ctx.fill()
                                    }
                                }
                            }
                        }
                        Canvas {
                            id: wireCanvas
                            anchors.fill: parent
                            z: 1
                            onPaint: {
                            var ctx = getContext("2d")
                            ctx.clearRect(0, 0, width, height)
                            ctx.lineCap = "round"
                            for (var i = 0; i < window.backend.connections.length; i++) {
                                var wire = window.backend.connections[i]
                                var from = window.positions[wire.source]
                                var to = window.positions[wire.target]
                                if (!from || !to)
                                    continue
                                var x1 = from.x + from.width
                                var y1 = from.y + wire.sourceOffset
                                var x2 = to.x
                                var y2 = to.y + wire.targetOffset
                                ctx.beginPath()
                                ctx.moveTo(x1, y1)
                                if (wire.routeStyle === "schematic") {
                                    if (wire.bypassRect && wire.bypassRect.length === 4) {
                                        var bypass = wire.bypassRect
                                        var bypassY = bypass[1] - 8
                                        ctx.lineTo(bypass[0] - 8, y1)
                                        ctx.lineTo(bypass[0] - 8, bypassY)
                                        ctx.lineTo(bypass[0] + bypass[2] + 8, bypassY)
                                        ctx.lineTo(bypass[0] + bypass[2] + 8, y1)
                                    }
                                    ctx.lineTo(wire.busX === undefined
                                        ? (x1 + x2) / 2 : wire.busX, y1)
                                    ctx.lineTo(wire.busX === undefined
                                        ? (x1 + x2) / 2 : wire.busX, y2)
                                    ctx.lineTo(x2, y2)
                                } else if (wire.wrapSide) {
                                    var wrapDirection = x2 >= x1 ? 1 : -1
                                    var wrapLaunchX = x1 + wrapDirection
                                            * (12 + wire.sourceRouteIndex * 6)
                                    var wrapApproachX = x2 - wrapDirection
                                            * (12 + wire.targetRouteIndex * 6)
                                    ctx.lineTo(wrapLaunchX, y1)
                                    ctx.lineTo(wrapLaunchX, wire.wrapLaneY)
                                    ctx.lineTo(wrapApproachX, wire.wrapLaneY)
                                    ctx.lineTo(wrapApproachX, y2)
                                    ctx.lineTo(x2, y2)
                                } else {
                                    var direction = x2 >= x1 ? 1 : -1
                                    var launchX = x1 + direction
                                            * (12 + wire.sourceRouteIndex * 6)
                                    var approachX = x2 - direction
                                            * (12 + wire.targetRouteIndex * 6)
                                    var channelX = launchX + (approachX - launchX)
                                            * wire.routeChannelFraction
                                    var laneY = (y1 + y2) / 2 + wire.routeLaneOffset
                                    ctx.lineTo(launchX, y1)
                                    ctx.lineTo(channelX, y1)
                                    ctx.lineTo(channelX, laneY)
                                    ctx.lineTo(approachX, laneY)
                                    ctx.lineTo(approachX, y2)
                                    ctx.lineTo(x2, y2)
                                }
                                ctx.strokeStyle = "#ffffff"
                                ctx.lineWidth = 6
                                ctx.stroke()
                                ctx.strokeStyle = wire.color || "#315eaa"
                                ctx.lineWidth = 3
                                ctx.stroke()
                            }
                            for (var junctionIndex = 0;
                                    junctionIndex < window.backend.connections.length;
                                    junctionIndex++) {
                                var junctionWire =
                                        window.backend.connections[junctionIndex]
                                if (!junctionWire.junction)
                                    continue
                                var junctionTarget =
                                        window.positions[junctionWire.target]
                                if (!junctionTarget)
                                    continue
                                var junctionY = junctionTarget.y
                                        + junctionWire.targetOffset
                                ctx.beginPath()
                                ctx.fillStyle = "#17233b"
                                ctx.arc(junctionWire.busX, junctionY, 3, 0,
                                    2 * Math.PI)
                                ctx.fill()
                            }
                        }
                    }
                        Repeater {
                            model: window.backend.schemeNodes
                            delegate: Rectangle {
                                id: gate
                                required property var modelData
                                property real currentX: modelData.x
                                property real currentY: modelData.y
                                x: currentX
                                y: currentY
                                width: modelData.width
                                height: modelData.height
                                z: 2
                                radius: 9
                                color: gate.modelData.style === "schematic"
                                    ? "transparent" : "#f2f6ff"
                                border.color: gate.modelData.style === "schematic"
                                    ? "transparent" : window.wireMode
                                        && window.connectionSource === modelData.id
                                    ? "#e28719" : "#315eaa"
                                border.width: gate.modelData.style === "schematic" ? 0 : 2

                                Canvas {
                                    id: symbol
                                    anchors.fill: parent
                                    onPaint: {
                                        var ctx = getContext("2d")
                                        ctx.clearRect(0, 0, width, height)
                                        ctx.strokeStyle = "#17233b"
                                        ctx.fillStyle = "#ffffff"
                                        ctx.lineWidth = 2
                                        var iconX = 23
                                        var iconY = 10
                                        if (gate.modelData.style === "schematic") {
                                            ctx.strokeStyle = "#17233b"
                                            ctx.fillStyle = "#ffffff"
                                            ctx.lineWidth = 1.8
                                            var centerY = height / 2
                                            for (var inputIndex = 0;
                                                    inputIndex < window.backend.connections.length;
                                                    inputIndex++) {
                                                var schematicInput =
                                                        window.backend.connections[inputIndex]
                                                if (schematicInput.target !== gate.modelData.id)
                                                    continue
                                                ctx.beginPath()
                                                ctx.moveTo(0, schematicInput.targetOffset)
                                                ctx.lineTo(gate.modelData.type === "OR" ? 20
                                                    : gate.modelData.type === "AND" ? 8
                                                    : gate.modelData.type === "NOT" ? 4 : 0,
                                                    schematicInput.targetOffset)
                                                ctx.stroke()
                                            }
                                            for (var outputIndex = 0;
                                                    outputIndex < window.backend.connections.length;
                                                    outputIndex++) {
                                                var schematicOutput =
                                                        window.backend.connections[outputIndex]
                                                if (schematicOutput.source !== gate.modelData.id)
                                                    continue
                                                var symbolEnd = gate.modelData.type === "OR"
                                                        ? width - 18
                                                        : gate.modelData.type === "AND" ? width - 16
                                                        : gate.modelData.type === "NOT" ? width - 9
                                                        : gate.modelData.type === "OUTPUT" ? width - 8
                                                        : gate.modelData.type === "INPUT" ? 15
                                                        : width - 8
                                                ctx.beginPath()
                                                ctx.moveTo(symbolEnd, schematicOutput.sourceOffset)
                                                ctx.lineTo(width, schematicOutput.sourceOffset)
                                                ctx.stroke()
                                            }
                                            ctx.beginPath()
                                            if (gate.modelData.type === "INPUT") {
                                                ctx.arc(9, centerY, 4, 0, 2 * Math.PI)
                                                ctx.stroke()
                                                ctx.beginPath()
                                                ctx.moveTo(13, centerY)
                                                ctx.lineTo(width, centerY)
                                                ctx.stroke()
                                            } else if (gate.modelData.type === "AND") {
                                                ctx.moveTo(8, 4)
                                                ctx.lineTo(width - 18, 4)
                                                ctx.arc(width - 18, centerY, height / 2 - 4,
                                                    -Math.PI / 2, Math.PI / 2)
                                                ctx.lineTo(8, height - 4)
                                                ctx.closePath()
                                                ctx.fill()
                                                ctx.stroke()
                                            } else if (gate.modelData.type === "OR") {
                                                ctx.moveTo(20, 4)
                                                ctx.quadraticCurveTo(36, centerY,
                                                    20, height - 4)
                                                ctx.quadraticCurveTo(width - 35, height - 4,
                                                    width - 18, centerY)
                                                ctx.quadraticCurveTo(width - 35, 4,
                                                    20, 4)
                                                ctx.closePath()
                                                ctx.fill()
                                                ctx.stroke()
                                            } else if (gate.modelData.type === "NOT") {
                                                ctx.moveTo(4, 4)
                                                ctx.lineTo(width - 16, centerY)
                                                ctx.lineTo(4, height - 4)
                                                ctx.closePath()
                                                ctx.fill()
                                                ctx.stroke()
                                                ctx.beginPath()
                                                ctx.arc(width - 9, centerY, 3.5,
                                                    0, 2 * Math.PI)
                                                ctx.fill()
                                                ctx.stroke()
                                            } else if (gate.modelData.type === "OUTPUT") {
                                                ctx.moveTo(0, centerY)
                                                ctx.lineTo(width - 9, centerY)
                                                ctx.stroke()
                                                ctx.beginPath()
                                                ctx.arc(width - 5, centerY, 4,
                                                    0, 2 * Math.PI)
                                                ctx.stroke()
                                            } else {
                                                ctx.rect(5, 4, width - 10, height - 8)
                                                ctx.fill()
                                                ctx.stroke()
                                                ctx.fillStyle = "#17233b"
                                                ctx.font = "bold 13px sans-serif"
                                                ctx.textAlign = "center"
                                                ctx.textBaseline = "middle"
                                                ctx.fillText(gate.modelData.label,
                                                    width / 2, centerY)
                                            }
                                            return
                                        }
                                        for (var i = 0; i < window.backend.connections.length; i++) {
                                            var wire = window.backend.connections[i]
                                            if (wire.target === gate.modelData.id) {
                                                ctx.beginPath()
                                                ctx.strokeStyle = wire.color || "#315eaa"
                                                ctx.moveTo(0, wire.targetOffset)
                                                ctx.lineTo(iconX + 3, wire.targetOffset)
                                                ctx.stroke()
                                            }
                                        }
                                        var outputStartX = gate.modelData.type === "NOT"
                                                ? iconX + 61
                                                : gate.modelData.type === "INPUT"
                                                    ? iconX + 54
                                                    : gate.modelData.type === "CONSTANT"
                                                        ? iconX + 56
                                                        : iconX + 55
                                        for (var j = 0; j < window.backend.connections.length; j++) {
                                            var outputWire = window.backend.connections[j]
                                            if (outputWire.source !== gate.modelData.id)
                                                continue
                                            ctx.beginPath()
                                            ctx.strokeStyle = outputWire.color || "#315eaa"
                                            ctx.moveTo(outputStartX, outputWire.sourceOffset)
                                            ctx.lineTo(width, outputWire.sourceOffset)
                                            ctx.stroke()
                                        }
                                        ctx.beginPath()
                                        ctx.strokeStyle = "#17233b"
                                        ctx.beginPath()
                                        if (gate.modelData.type === "AND") {
                                            ctx.moveTo(iconX + 3, iconY + 10)
                                            ctx.lineTo(iconX + 28, iconY + 10)
                                            ctx.arc(iconX + 28, iconY + 36, 26,
                                                -Math.PI / 2, Math.PI / 2)
                                            ctx.lineTo(iconX + 3, iconY + 62)
                                            ctx.closePath()
                                            ctx.fill()
                                            ctx.stroke()
                                        } else if (gate.modelData.type === "OR") {
                                            ctx.moveTo(iconX + 3, iconY + 8)
                                            ctx.quadraticCurveTo(iconX + 20, 46,
                                                iconX + 3, iconY + 68)
                                            ctx.quadraticCurveTo(iconX + 36, 68,
                                                iconX + 60, 50)
                                            ctx.quadraticCurveTo(iconX + 36, 32,
                                                iconX + 3, iconY + 8)
                                            ctx.closePath()
                                            ctx.fill()
                                            ctx.stroke()
                                        } else if (gate.modelData.type === "NOT") {
                                            ctx.moveTo(iconX + 6, iconY + 14)
                                            ctx.lineTo(iconX + 49, 50)
                                            ctx.lineTo(iconX + 6, iconY + 58)
                                            ctx.closePath()
                                            ctx.fill()
                                            ctx.stroke()
                                            ctx.beginPath()
                                            ctx.arc(iconX + 55, 50, 5, 0, 2 * Math.PI)
                                            ctx.fill()
                                            ctx.stroke()
                                        } else if (gate.modelData.type === "INPUT") {
                                            ctx.arc(iconX + 30, 49, 21, 0, 2 * Math.PI)
                                            ctx.fill()
                                            ctx.stroke()
                                        } else if (gate.modelData.type === "OUTPUT") {
                                            ctx.moveTo(iconX + 3, 50)
                                            ctx.lineTo(iconX + 49, 50)
                                            ctx.stroke()
                                            ctx.beginPath()
                                            ctx.arc(iconX + 54, 50, 5, 0, 2 * Math.PI)
                                            ctx.fill()
                                            ctx.stroke()
                                        } else {
                                            ctx.rect(iconX + 4, iconY + 12, 52, 50)
                                            ctx.fill()
                                            ctx.stroke()
                                            if (gate.modelData.type === "CONSTANT") {
                                                ctx.fillStyle = "#17233b"
                                                ctx.font = "bold 22px sans-serif"
                                                ctx.textAlign = "center"
                                                ctx.textBaseline = "middle"
                                                ctx.fillText(gate.modelData.label,
                                                    iconX + 30, 47)
                                            }
                                        }
                                        }
                                    }
                                Label {
                                    visible: gate.modelData.style !== "schematic"
                                        || ["INPUT", "NOT", "OUTPUT"].indexOf(
                                            gate.modelData.type) >= 0
                                    x: gate.modelData.style === "schematic"
                                        ? gate.modelData.type === "INPUT" ? -25
                                            : gate.modelData.type === "OUTPUT"
                                                ? parent.width + 2 : 0
                                        : 4
                                    y: gate.modelData.style === "schematic"
                                        ? gate.modelData.type === "NOT"
                                            ? parent.height + 1 : 0
                                        : parent.height - 23
                                    width: gate.modelData.style === "schematic"
                                        ? gate.modelData.type === "INPUT"
                                            ? 22 : gate.modelData.type === "OUTPUT" ? 30 : parent.width
                                        : parent.width - 8
                                    height: 20
                                    horizontalAlignment: gate.modelData.style === "schematic"
                                        && gate.modelData.type === "INPUT"
                                        ? Text.AlignRight : Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                    text: gate.modelData.label
                                    elide: Text.ElideRight
                                    font.pixelSize: gate.modelData.style === "schematic"
                                        ? 12 : 10
                                    font.bold: true
                                    color: "#26354f"
                                }
                                TapHandler {
                                    onTapped: {
                                        if (!window.wireMode)
                                            return
                                        if (!window.connectionSource) {
                                            window.connectionSource = gate.modelData.id
                                        } else {
                                            window.backend.connectNodes(
                                                window.connectionSource, gate.modelData.id
                                            )
                                            window.connectionSource = ""
                                            window.wireMode = false
                                        }
                                    }
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    acceptedButtons: Qt.NoButton
                                    cursorShape: Qt.OpenHandCursor
                                }
                                DragHandler {
                                    id: dragHandler
                                    target: null
                                    property point origin
                                    onActiveChanged: {
                                        if (active) {
                                            origin = Qt.point(gate.currentX, gate.currentY)
                                        } else {
                                            window.backend.moveNode(gate.modelData.id, gate.currentX, gate.currentY)
                                        }
                                    }
                                    onTranslationChanged: {
                                        if (!active)
                                            return
                                        var nextX = origin.x + translation.x
                                        var nextY = origin.y + translation.y
                                        gate.currentX = Math.max(0, Math.min(
                                            nextX, window.backend.schemeWidth - gate.width
                                        ))
                                        gate.currentY = Math.max(0, Math.min(
                                            nextY, window.backend.schemeHeight - gate.height
                                        ))
                                        window.updatePosition(
                                            gate.modelData.id, gate.currentX, gate.currentY
                                        )
                                    }
                                }
                            }
                        }
                    }
                        Label {
                            anchors.left: parent.left
                            anchors.bottom: parent.bottom
                            anchors.margins: 12
                            text: window.backend.error
                                ? window.backend.error
                                : window.backend.schemeKind === "MUX"
                                    ? qsTr("MUX decomposition of the selected f · drag gates to rearrange")
                                : window.backend.hasAnyResult
                                    ? qsTr("Generated from the current function · press Ctrl+Z to undo scheme edits")
                                    : qsTr("Add a gate or calculate a canonical form to build the scheme.")
                            color: window.backend.error ? "#b3261e" : "#46546c"
                            font.pixelSize: 12
                            z: 3
                    }
                }
            }
        }
    }

    FileDialog {
        id: pdfDialog
        title: qsTr("Export Boolean logic as PDF")
        fileMode: FileDialog.SaveFile
        nameFilters: ["PDF files (*.pdf)"]
        defaultSuffix: "pdf"
        onAccepted: window.backend.exportPdf(selectedFile.toString())
    }

    Shortcut {
        sequence: "Ctrl+Z"
        enabled: tabs.currentIndex === 2 && !newGateLabel.activeFocus
        onActivated: window.backend.undoScheme()
    }

    Connections {
        target: window.backend
        function onSchemeChanged() {
            window.refreshPositions()
        }
    }
}
