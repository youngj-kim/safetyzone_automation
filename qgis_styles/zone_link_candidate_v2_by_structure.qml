<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.34" styleCategories="Symbology">
  <renderer-v2 type="categorizedSymbol" attr="link_structure_category" symbollevels="0" enableorderby="0" forceraster="0">
    <categories>
      <category value="NORMAL_ROAD" label="일반도로" symbol="0" render="true"/>
      <category value="ELEVATED_ROAD_REVIEW" label="고가차도 검토" symbol="1" render="true"/>
      <category value="UNDERPASS_REVIEW" label="지하차도 검토" symbol="2" render="true"/>
      <category value="BRIDGE_REVIEW" label="교량 검토" symbol="3" render="true"/>
      <category value="TUNNEL_REVIEW" label="터널 검토" symbol="4" render="true"/>
      <category value="RAMP_CONNECTOR_REVIEW" label="연결로/램프 검토" symbol="5" render="true"/>
      <category value="STRUCTURE_REVIEW" label="기타 구조 검토" symbol="6" render="true"/>
    </categories>
    <symbols>
      <symbol name="0" type="line" clip_to_extent="1" alpha="1">
        <layer enabled="1" class="SimpleLine" pass="0">
          <Option type="Map">
            <Option name="line_color" type="QString" value="220,20,60,255"/>
            <Option name="line_width" type="QString" value="1.2"/>
            <Option name="line_style" type="QString" value="solid"/>
          </Option>
        </layer>
      </symbol>
      <symbol name="1" type="line" clip_to_extent="1" alpha="1">
        <layer enabled="1" class="SimpleLine" pass="0">
          <Option type="Map">
            <Option name="line_color" type="QString" value="255,215,0,255"/>
            <Option name="line_width" type="QString" value="1.8"/>
            <Option name="line_style" type="QString" value="dash"/>
          </Option>
        </layer>
      </symbol>
      <symbol name="2" type="line" clip_to_extent="1" alpha="1">
        <layer enabled="1" class="SimpleLine" pass="0">
          <Option type="Map">
            <Option name="line_color" type="QString" value="0,140,255,255"/>
            <Option name="line_width" type="QString" value="1.8"/>
            <Option name="line_style" type="QString" value="dash"/>
          </Option>
        </layer>
      </symbol>
      <symbol name="3" type="line" clip_to_extent="1" alpha="1">
        <layer enabled="1" class="SimpleLine" pass="0">
          <Option type="Map">
            <Option name="line_color" type="QString" value="148,0,211,255"/>
            <Option name="line_width" type="QString" value="1.7"/>
            <Option name="line_style" type="QString" value="dash dot"/>
          </Option>
        </layer>
      </symbol>
      <symbol name="4" type="line" clip_to_extent="1" alpha="1">
        <layer enabled="1" class="SimpleLine" pass="0">
          <Option type="Map">
            <Option name="line_color" type="QString" value="40,40,40,255"/>
            <Option name="line_width" type="QString" value="1.8"/>
            <Option name="line_style" type="QString" value="dot"/>
          </Option>
        </layer>
      </symbol>
      <symbol name="5" type="line" clip_to_extent="1" alpha="1">
        <layer enabled="1" class="SimpleLine" pass="0">
          <Option type="Map">
            <Option name="line_color" type="QString" value="255,128,0,255"/>
            <Option name="line_width" type="QString" value="1.8"/>
            <Option name="line_style" type="QString" value="solid"/>
          </Option>
        </layer>
      </symbol>
      <symbol name="6" type="line" clip_to_extent="1" alpha="1">
        <layer enabled="1" class="SimpleLine" pass="0">
          <Option type="Map">
            <Option name="line_color" type="QString" value="128,128,128,255"/>
            <Option name="line_width" type="QString" value="1.2"/>
            <Option name="line_style" type="QString" value="dash"/>
          </Option>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
</qgis>
