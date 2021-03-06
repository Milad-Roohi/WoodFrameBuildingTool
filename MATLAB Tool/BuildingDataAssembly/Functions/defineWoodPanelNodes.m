
% This function is used to generate an array of wood panel node objects
% (x- and z-panel nodes defined separately) containing the node number,
% x, z and y coordinates OpenSees tag and floor level for that node.

% xWoodPanelNodeObject = xWoodPanelNode(number, level, ...
% xCoordinate, zCoordinate, yCoordinate, topOrBottomNode, panelNumber)

function [XDirectionWoodPanelNodes, ZDirectionWoodPanelNodes] = ...
    defineWoodPanelNodes(buildingGeometry, ClassesDirectory)

% Create empty array to store wood panel nodes
cd(ClassesDirectory);

% XDirectionWoodPanelNodes is an M X N cell where M is the number of
% stories in the building and N is the maximum number of x-direction
% wood panels on all floors.

% Each cell entry is a xWoodPanelNode object which contains the node
% number, x, z and y coordinates, OpenSees tag and floor level for that
% node.
XDirectionWoodPanelNodes = cell(buildingGeometry.numberOfStories,...
    max(buildingGeometry.numberOfXDirectionWoodPanels));
ZDirectionWoodPanelNodes = cell(buildingGeometry.numberOfStories,...
    max(buildingGeometry.numberOfZDirectionWoodPanels));

% Variable used to count number of wood panel nodes
xCount = 1;
zCount = 1;

% Loop over the number of stories
for i = 1:buildingGeometry.numberOfStories
    
    % Loop over the number of X-Direction wood panels
    for j = 1:buildingGeometry.numberOfXDirectionWoodPanels(i,1)
        % Node at bottom of panel
        XDirectionWoodPanelNodes{i,j} = ...
            [saveToStruct(xWoodPanelNode(xCount, i, ...
            buildingGeometry.XDirectionWoodPanelsXCoordinates(i,j),...
            buildingGeometry.XDirectionWoodPanelsZCoordinates(i,j),...
            buildingGeometry.floorHeights(i,1), 1, j));...
            ...
            saveToStruct(xWoodPanelNode(xCount + 1,i + 1,...
            buildingGeometry.XDirectionWoodPanelsXCoordinates(i,j),...
            buildingGeometry.XDirectionWoodPanelsZCoordinates(i,j),...
            buildingGeometry.floorHeights(i + 1,1), 2, j))];
        
        xCount = xCount + 2;
        
    end
    
    % Loop over the number of Z-Direction wood panels
    for j = 1:buildingGeometry.numberOfZDirectionWoodPanels(i,1)
        % Node at bottom of panel
        ZDirectionWoodPanelNodes{i,j} = ...
            [saveToStruct(zWoodPanelNode(zCount, i, ...
            buildingGeometry.ZDirectionWoodPanelsXCoordinates(i,j),...
            buildingGeometry.ZDirectionWoodPanelsZCoordinates(i,j),...
            buildingGeometry.floorHeights(i,1), 1, j));...
            ...
            saveToStruct(zWoodPanelNode(zCount + 1, i + 1,...
            buildingGeometry.ZDirectionWoodPanelsXCoordinates(i,j),...
            buildingGeometry.ZDirectionWoodPanelsZCoordinates(i,j),...
            buildingGeometry.floorHeights(i + 1,1), 2, j))];
        
        zCount = zCount + 2;
        
    end
end
end

