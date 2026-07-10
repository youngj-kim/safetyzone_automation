<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.34" styleCategories="Symbology">
  <renderer-v2 type="categorizedSymbol" attr="v23_review_bucket" symbollevels="0" enableorderby="0" forceraster="0">
    <categories>
      <category value="EXCLUDED_VALID" label="EXCLUDED_VALID" symbol="0" render="true"/>
      <category value="POSSIBLE_FALSE_NEGATIVE_CONTINUOUS_CORRIDOR" label="POSSIBLE_FALSE_NEGATIVE_CONTINUOUS_CORRIDOR" symbol="1" render="true"/>
      <category value="MANUAL_REVIEW_STRUCTURE_EXCLUDED" label="MANUAL_REVIEW_STRUCTURE_EXCLUDED" symbol="2" render="true"/>
      <category value="NO_SEED_REVIEW" label="NO_SEED_REVIEW" symbol="3" render="true"/>
      <category value="EXCLUDED_REVIEW_OTHER" label="EXCLUDED_REVIEW_OTHER" symbol="4" render="true"/>
    </categories>
    <symbols>
      <symbol name="0" type="line" clip_to_extent="1" alpha="0.65">
        <layer enabled="1" class="SimpleLine" pass="0">
          <Option type="Map">
            <Option name="line_color" type="QString" value="90,90,90,255"/>
            <Option name="line_width" type="QString" value="1.0"/>
            <Option name="line_style" type="QString" value="dot"/>
          </Option>
        </layer>
      </symbol>
      <symbol name="1" type="line" clip_to_extent="1" alpha="1">
        <layer enabled="1" class="SimpleLine" pass="0">
          <Option type="Map">
            <Option name="line_color" type="QString" value="255,0,0,255"/>
            <Option name="line_width" type="QString" value="2.2"/>
            <Option name="line_style" type="QString" value="dash"/>
          </Option>
        </layer>
      </symbol>
      <symbol name="2" type="line" clip_to_extent="1" alpha="1">
        <layer enabled="1" class="SimpleLine" pass="0">
          <Option type="Map">
            <Option name="line_color" type="QString" value="255,215,0,255"/>
            <Option name="line_width" type="QString" value="1.8"/>
            <Option name="line_style" type="QString" value="dash"/>
          </Option>
        </layer>
      </symbol>
      <symbol name="3" type="line" clip_to_extent="1" alpha="0.85">
        <layer enabled="1" class="SimpleLine" pass="0">
          <Option type="Map">
            <Option name="line_color" type="QString" value="0,140,255,255"/>
            <Option name="line_width" type="QString" value="1.5"/>
            <Option name="line_style" type="QString" value="dash dot"/>
          </Option>
        </layer>
      </symbol>
      <symbol name="4" type="line" clip_to_extent="1" alpha="0.8">
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
