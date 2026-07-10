<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.34" styleCategories="Symbology">
  <renderer-v2 type="categorizedSymbol" attr="v23_review_bucket" symbollevels="0" enableorderby="0" forceraster="0">
    <categories>
      <category value="AUTO_APPLY_CANDIDATE" label="AUTO_APPLY_CANDIDATE" symbol="0" render="true"/>
      <category value="MANUAL_REVIEW_STRUCTURE" label="MANUAL_REVIEW_STRUCTURE" symbol="1" render="true"/>
      <category value="MANUAL_REVIEW_A_NEAR_OR_JUNCTION" label="MANUAL_REVIEW_A_NEAR_OR_JUNCTION" symbol="2" render="true"/>
      <category value="MANUAL_REVIEW_WEAK_OVERLAP" label="MANUAL_REVIEW_WEAK_OVERLAP" symbol="3" render="true"/>
      <category value="MANUAL_REVIEW_CONNECTED" label="MANUAL_REVIEW_CONNECTED" symbol="4" render="true"/>
      <category value="MANUAL_REVIEW_OTHER" label="MANUAL_REVIEW_OTHER" symbol="5" render="true"/>
    </categories>
    <symbols>
      <symbol name="0" type="line" clip_to_extent="1" alpha="1">
        <layer enabled="1" class="SimpleLine" pass="0">
          <Option type="Map">
            <Option name="line_color" type="QString" value="220,20,60,255"/>
            <Option name="line_width" type="QString" value="1.7"/>
            <Option name="line_style" type="QString" value="solid"/>
          </Option>
        </layer>
      </symbol>
      <symbol name="1" type="line" clip_to_extent="1" alpha="1">
        <layer enabled="1" class="SimpleLine" pass="0">
          <Option type="Map">
            <Option name="line_color" type="QString" value="255,215,0,255"/>
            <Option name="line_width" type="QString" value="2.0"/>
            <Option name="line_style" type="QString" value="dash"/>
          </Option>
        </layer>
      </symbol>
      <symbol name="2" type="line" clip_to_extent="1" alpha="1">
        <layer enabled="1" class="SimpleLine" pass="0">
          <Option type="Map">
            <Option name="line_color" type="QString" value="0,110,220,255"/>
            <Option name="line_width" type="QString" value="1.8"/>
            <Option name="line_style" type="QString" value="solid"/>
          </Option>
        </layer>
      </symbol>
      <symbol name="3" type="line" clip_to_extent="1" alpha="1">
        <layer enabled="1" class="SimpleLine" pass="0">
          <Option type="Map">
            <Option name="line_color" type="QString" value="255,140,0,255"/>
            <Option name="line_width" type="QString" value="1.8"/>
            <Option name="line_style" type="QString" value="solid"/>
          </Option>
        </layer>
      </symbol>
      <symbol name="4" type="line" clip_to_extent="1" alpha="1">
        <layer enabled="1" class="SimpleLine" pass="0">
          <Option type="Map">
            <Option name="line_color" type="QString" value="128,0,255,255"/>
            <Option name="line_width" type="QString" value="1.5"/>
            <Option name="line_style" type="QString" value="dash dot"/>
          </Option>
        </layer>
      </symbol>
      <symbol name="5" type="line" clip_to_extent="1" alpha="1">
        <layer enabled="1" class="SimpleLine" pass="0">
          <Option type="Map">
            <Option name="line_color" type="QString" value="128,128,128,255"/>
            <Option name="line_width" type="QString" value="1.2"/>
            <Option name="line_style" type="QString" value="dot"/>
          </Option>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
</qgis>
