import { observer } from "mobx-react-lite";
import { useCallback, useState } from "react";

import { Button, InputNumber, Space } from "@nextgisweb/gui/antd";
import { useAbortController } from "@nextgisweb/pyramid/hook";
import { gettext } from "@nextgisweb/pyramid/i18n";
import { showResourcePicker } from "@nextgisweb/resource/component/resource-picker";
import type { ResourcePickerStoreOptions } from "@nextgisweb/resource/component/resource-picker/type";

import type { Extent } from "../type";
import { getExtentFromLayer } from "../util/getExtentFromLayer";

import LayersIconOutlined from "@nextgisweb/icon/material/layers";

import "./ExtentRow.less";

interface ExtentRow {
    value: Extent;
    onChange: (val: Extent) => void;
    pickerOptions?: ResourcePickerStoreOptions;
}

export const ExtentRow = observer(
    ({ value, onChange, pickerOptions }: ExtentRow) => {
        const [loading, setIsLoading] = useState(false);

        const { makeSignal } = useAbortController();

        const onSetFromLayerClick = useCallback(() => {
            showResourcePicker({
                pickerOptions: {
                    requireInterface: "IBboxLayer",
                    ...pickerOptions,
                },
                onSelect: async (resourceId: number) => {
                    setIsLoading(true);
                    try {
                        const res = await getExtentFromLayer({
                            resourceId,
                            signal: makeSignal(),
                        });
                        onChange(res);
                    } finally {
                        setIsLoading(false);
                    }
                },
            });
        }, [makeSignal, onChange, pickerOptions]);

        return (
            <div className="ngw-webmap-settings-widget-extent-row">
                <Button
                    loading={loading}
                    icon={<LayersIconOutlined />}
                    onClick={onSetFromLayerClick}
                >
                    {gettext("From layer")}
                </Button>
                <Space.Compact style={{ display: "flex" }}>
                    <InputNumber
                        value={value.left}
                        onChange={(left) => {
                            onChange({ ...value, left });
                        }}
                        addonBefore={gettext("West")}
                        precision={4}
                        max={180}
                        min={-180}
                        controls={false}
                    />
                    <InputNumber
                        value={value.bottom}
                        onChange={(bottom) => {
                            onChange({ ...value, bottom });
                        }}
                        addonBefore={gettext("South")}
                        precision={4}
                        max={90}
                        min={-90}
                        controls={false}
                    />
                    <InputNumber
                        value={value.right}
                        onChange={(right) => onChange({ ...value, right })}
                        addonBefore={gettext("East")}
                        precision={4}
                        max={180}
                        min={-180}
                        controls={false}
                    />
                    <InputNumber
                        value={value.top}
                        onChange={(top) => onChange({ ...value, top })}
                        addonBefore={gettext("North")}
                        precision={4}
                        max={90}
                        min={-90}
                        controls={false}
                    />
                </Space.Compact>
            </div>
        );
    }
);

ExtentRow.displayName = "ExtentRow";
