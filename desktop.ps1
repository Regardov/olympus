param(
    [ValidateSet('tech','lab')] [string]$Module = 'tech',
    [int]$Port = 8765,
    [switch]$Smoke
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$script:apiBase = "http://127.0.0.1:$Port/api/"
$script:token = $null
$script:user = $null
$script:moduleName = if ($Module -eq 'tech') { 'Рабочее место технолога' } else { 'Лаборатория качества' }
$script:ink = [Drawing.ColorTranslator]::FromHtml('#192C34')
$script:nav = [Drawing.ColorTranslator]::FromHtml('#172831')
$script:teal = [Drawing.ColorTranslator]::FromHtml('#156352')
$script:paper = [Drawing.ColorTranslator]::FromHtml('#F1F5F5')
$script:muted = [Drawing.ColorTranslator]::FromHtml('#50656E')
$script:accent = [Drawing.ColorTranslator]::FromHtml('#FAC369')
$script:states = @{
    active='Действует'; archived='Архив'; draft='Черновик'; review='На согласовании'; planned='Запланирована'
    in_progress='В работе'; quality='Контроль качества'; completed='Завершена'; cancelled='Отменён'; blocked='Заблокирована'
    pending='Ожидает'; released='Допущена'; ready='Готов'; running='Выполняется'; done='Завершено'; skipped='Пропущен'
    open='Открыто'; resolved='Устранён'; pass='Соответствует'; fail='Не соответствует'
    raw='Сырьё'; mass='Масса'; glaze='Глазурь'; finished='Готовая продукция'; warning='Предупреждение'; critical='Критический'
}
$script:colNames = @{
    id='ID'; code='Код / номер'; name='Наименование'; product='Продукт'; type='Тип'; format='Формат'; collection='Коллекция'
    surface='Поверхность'; status='Статус'; mass='Масса, вер.'; glaze='Глазурь, вер.'; card='Карта, вер.'
    kind='Вид'; version='Версия'; author='Автор'; created='Создано (UTC)'; due='Срок'; quantity='Количество'
    line='Линия'; current_step='Текущий шаг'; done='Шагов готово'; total='Всего'; warning='Предупр.'; critical='Критич.'
    order_code='Заказ'; temperature='Темп., °C'; duration='Время, мин'; pressure='Давление, бар'; notes='Примечание'
    equipment='Оборудование'; action='Событие'; detail='Детали'; batch='Партия'; severity='Уровень'; state='Состояние'
    description='Описание'; resolution='Решение'; comment='Комментарий'; material='Материал'; supplier_code='Номер поставщика'
    category='Категория'; supplier='Поставщик'; received='Поступление'; unit='Ед.'; location='Место хранения'
    last_test='Последнее испытание'; analyst='Исполнитель'; priority='Приоритет'; result='Результат'; decision='Решение'
    appointed='Назначено'; finished='Завершено'; target='Объект / план'; value='Факт'; minimum='Мин.'; maximum='Макс.'
    position='№'; instructions='Инструкция'; required='Обяз.'; parameter='Параметр'; step='Шаг'; deviation='Отклонение'
    share='Доля, %'; tolerance='Допуск, %'; zone='Зона'; batches='Партий'; started='Начало'; product_code='Код продукта'
    mass_version='Версия массы'; glaze_version='Версия глазури'; card_version='Версия карты'; login='Логин'; role='Роль'
    department='Подразделение'; shift='Смена'; password='Пароль'
}

function Invoke-Api([string]$Path,[string]$Method='GET',$Body=$null) {
    $params = @{ Uri=$script:apiBase+$Path; Method=$Method; TimeoutSec=8; ErrorAction='Stop' }
    if ($script:token) { $params.Headers=@{Authorization="Bearer $script:token"} }
    if ($null -ne $Body) {
        $params.ContentType='application/json; charset=utf-8'
        $params.Body=[Text.Encoding]::UTF8.GetBytes((ConvertTo-Json -InputObject $Body -Depth 20 -Compress))
    }
    try { return (Invoke-RestMethod @params).data }
    catch {
        $message = $_.ErrorDetails.Message
        if ($message) {
            try { $packet=$message | ConvertFrom-Json } catch { $packet=$null }
            if ($packet.error) { throw $packet.error }
        }
        if ($_.Exception.Response) {
            try {
                $reader=[IO.StreamReader]::new($_.Exception.Response.GetResponseStream(),[Text.Encoding]::UTF8)
                $packet=$reader.ReadToEnd() | ConvertFrom-Json
                $reader.Dispose()
            } catch { $packet=$null }
            if ($packet.error) { throw $packet.error }
        }
        throw "Не удалось обратиться к API. $($_.Exception.Message)"
    }
}

function Run-Safely([scriptblock]$Action) {
    try { & $Action }
    catch {
        [void][Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Ceramika',
            [Windows.Forms.MessageBoxButtons]::OK,[Windows.Forms.MessageBoxIcon]::Warning)
    }
}

function New-Label([string]$Text,[int]$Size=10,[switch]$Bold) {
    $label = [Windows.Forms.Label]::new()
    $label.Text=$Text; $label.AutoSize=$true; $label.ForeColor=$script:ink
    $style = if ($Bold) { [Drawing.FontStyle]::Bold } else { [Drawing.FontStyle]::Regular }
    $label.Font=[Drawing.Font]::new('Segoe UI',$Size,$style)
    return $label
}

function New-Button([string]$Text,[switch]$Primary) {
    $button=[Windows.Forms.Button]::new()
    $button.Text=$Text; $button.AutoSize=$true; $button.MinimumSize=[Drawing.Size]::new(84,34)
    $button.Padding=[Windows.Forms.Padding]::new(8,0,8,0); $button.FlatStyle='Flat'
    $button.FlatAppearance.BorderColor=[Drawing.ColorTranslator]::FromHtml('#C9D7DA')
    $button.BackColor=[Drawing.Color]::White; $button.ForeColor=$script:ink
    if ($Primary) { $button.BackColor=$script:teal; $button.ForeColor=[Drawing.Color]::White; $button.FlatAppearance.BorderSize=0 }
    return $button
}

function New-Flow([string]$Dock='Top',[int]$Height=42) {
    $bar=[Windows.Forms.FlowLayoutPanel]::new()
    $bar.Dock=$Dock; $bar.Height=$Height; $bar.WrapContents=$false
    return $bar
}

function New-Form([string]$Title,[int]$Width,[int]$Height) {
    $form=[Windows.Forms.Form]::new()
    $form.Text=$Title; $form.ClientSize=[Drawing.Size]::new($Width,$Height)
    $form.StartPosition='CenterScreen'; $form.BackColor=$script:paper
    $form.Font=[Drawing.Font]::new('Segoe UI',10)
    return $form
}

function Get-Val($Item,[string]$Field) {
    if ($null -eq $Item) { return $null }
    if ($Item -is [Collections.IDictionary]) { return $Item[$Field] }
    return $Item.$Field
}

function Display-Val($Value) {
    if ($null -eq $Value -or [string]$Value -eq '') { return '—' }
    if ($script:states.ContainsKey([string]$Value)) { return $script:states[[string]$Value] }
    if ($Value -is [bool]) { if ($Value) { return 'Да' } else { return 'Нет' } }
    return [string]$Value
}

function Field([string]$Key,[string]$Label,[string]$Type='text',$Value=$null,$Options=@()) {
    return @{key=$Key; label=$Label; type=$Type; value=$Value; options=@($Options)}
}

function Option($Key,[string]$Label) { return [pscustomobject]@{key=$Key; label=$Label} }

function Item-Options($Items,[string]$Field='name',[string]$Prefix='') {
    foreach($item in $Items) {
        $title=Get-Val $item $Field
        if ($Prefix) { $title="$(Get-Val $item $Prefix) · $title" }
        Option $item.id $title
    }
}

function Edit-Form([string]$Title,$Fields,[string]$Confirm='Сохранить',[string]$Note='') {
    $height=[Math]::Min(680,105 + $Fields.Count*51 + $(if($Note){45}else{0}))
    $dialog=New-Form $Title 640 $height
    $dialog.StartPosition='CenterParent'; $dialog.MinimizeBox=$false; $dialog.MaximizeBox=$false
    $dialog.Padding=[Windows.Forms.Padding]::new(18)
    $fieldsPanel=[Windows.Forms.Panel]::new(); $fieldsPanel.Dock='Fill'; $fieldsPanel.AutoScroll=$true
    $bar=New-Flow 'Bottom' 44
    $ok=New-Button $Confirm -Primary; $ok.DialogResult='OK'
    $cancel=New-Button 'Отмена'; $cancel.DialogResult='Cancel'
    $bar.Controls.AddRange(@($ok,$cancel)); $dialog.AcceptButton=$ok; $dialog.CancelButton=$cancel
    $dialog.Controls.AddRange(@($fieldsPanel,$bar))
    $inputs=@{}; $y=6
    if ($Note) {
        $noteLabel=New-Label $Note; $noteLabel.AutoSize=$false
        $noteLabel.Size=[Drawing.Size]::new(570,38); $noteLabel.Location=[Drawing.Point]::new(3,$y)
        $fieldsPanel.Controls.Add($noteLabel); $y+=44
    }
    foreach ($f in $Fields) {
        $label=New-Label $f.label; $label.Location=[Drawing.Point]::new(3,($y+4)); $label.MaximumSize=[Drawing.Size]::new(238,0)
        if ($f.type -eq 'choice') {
            $input=[Windows.Forms.ComboBox]::new(); $input.DropDownStyle='DropDownList'; $input.DisplayMember='label'
            $pick=-1
            foreach ($op in $f.options) {
                $i=$input.Items.Add($op)
                if ([string]$op.key -eq [string]$f.value) { $pick=$i }
            }
            if ($pick -ge 0) { $input.SelectedIndex=$pick } elseif ($input.Items.Count) { $input.SelectedIndex=0 }
        } else {
            $input=[Windows.Forms.TextBox]::new(); $input.Text=[string]$f.value
            if ($f.type -eq 'password') { $input.UseSystemPasswordChar=$true }
            if ($f.type -eq 'long') { $input.Multiline=$true; $input.Height=63; $input.ScrollBars='Vertical' }
            if ($f.type -eq 'read') { $input.ReadOnly=$true }
        }
        $input.Location=[Drawing.Point]::new(244,$y); $input.Width=336
        $fieldsPanel.Controls.AddRange(@($label,$input)); $inputs[$f.key]=$input
        $y+=$(if($f.type -eq 'long'){76}else{43})
    }
    $result=$null
    if ($dialog.ShowDialog() -eq 'OK') {
        $result=[ordered]@{}
        foreach($f in $Fields) {
            $input=$inputs[$f.key]
            $result[$f.key]=if ($f.type -eq 'choice') { $input.SelectedItem.key } else { $input.Text.Trim() }
        }
    }
    $dialog.Dispose()
    return $result
}

function New-Grid($Fields) {
    $grid=[Windows.Forms.DataGridView]::new()
    $grid.Dock='Fill'; $grid.ReadOnly=$true; $grid.RowHeadersVisible=$false; $grid.MultiSelect=$false
    $grid.AllowUserToAddRows=$false; $grid.AllowUserToDeleteRows=$false; $grid.SelectionMode='FullRowSelect'
    $grid.AutoSizeColumnsMode='Fill'; $grid.BorderStyle='None'; $grid.BackgroundColor=[Drawing.Color]::White
    $grid.GridColor=[Drawing.ColorTranslator]::FromHtml('#E1E8EA')
    $grid.RowTemplate.Height=33; $grid.ColumnHeadersHeight=39; $grid.EnableHeadersVisualStyles=$false
    $grid.ColumnHeadersDefaultCellStyle.BackColor=[Drawing.ColorTranslator]::FromHtml('#DBE7E7')
    $grid.ColumnHeadersDefaultCellStyle.ForeColor=$script:ink
    $grid.DefaultCellStyle.SelectionBackColor=$script:teal
    $grid.AlternatingRowsDefaultCellStyle.BackColor=[Drawing.ColorTranslator]::FromHtml('#F5F8F8')
    foreach($f in $Fields) {
        $label=if($script:colNames.ContainsKey($f)){$script:colNames[$f]}else{$f}
        $index=$grid.Columns.Add($f,$label)
        $grid.Columns[$index].MinimumWidth=70
        if($f -in @('description','instructions','detail','name','product','material')) { $grid.Columns[$index].FillWeight=150 }
    }
    return $grid
}

function Grid-Data($Grid,$Items) {
    $Grid.Rows.Clear()
    foreach($item in $Items) {
        if($null -eq $item){ continue }
        $values=[object[]]@($Grid.Columns | ForEach-Object { Display-Val (Get-Val $item $_.Name) })
        $index=$Grid.Rows.Add($values)
        $row=$Grid.Rows[$index]; $row.Tag=$item
        foreach($field in @('status','state','severity','decision','result')) {
            if (-not $Grid.Columns.Contains($field)) { continue }
            $color=switch (Get-Val $item $field) {
                {$_ -in @('blocked','critical','fail')} { '#FCEAEA' }
                {$_ -in @('quality','warning','review','open','pending')} { '#FFF1D7' }
                {$_ -in @('released','active','completed','in_progress','resolved','pass','done')} { '#E2F3EB' }
            }
            if($color){$row.Cells[$field].Style.BackColor=[Drawing.ColorTranslator]::FromHtml($color)}
        }
    }
    $Grid.ClearSelection()
}

function Selected($Grid) {
    if ($Grid.SelectedRows.Count -eq 0) { throw 'Сначала выберите строку.' }
    return $Grid.SelectedRows[0].Tag
}

function Add-Action($Bar,[string]$Name,[scriptblock]$Action,[switch]$Primary) {
    $button=New-Button $Name -Primary:$Primary; $button.Tag=$Action
    $button.Add_Click({ param($sender,$eventArgs) Run-Safely $sender.Tag })
    $Bar.Controls.Add($button)
}

function Show-Tables([string]$Title,[string]$Summary,$Tables) {
    $dialog=New-Form $Title 1040 595; $dialog.StartPosition='CenterParent'; $dialog.Padding=[Windows.Forms.Padding]::new(16)
    $header=[Windows.Forms.TextBox]::new(); $header.Multiline=$true; $header.ReadOnly=$true
    $header.Height=105; $header.ScrollBars='Vertical'; $header.Text=$Summary; $header.Dock='Top'
    $tabs=[Windows.Forms.TabControl]::new(); $tabs.Dock='Fill'
    foreach($table in $Tables) {
        $page=[Windows.Forms.TabPage]::new($table.title)
        $grid=New-Grid $table.columns; Grid-Data $grid $table.items
        $page.Controls.Add($grid); $tabs.TabPages.Add($page)
    }
    $dialog.Controls.AddRange(@($tabs,$header)); [void]$dialog.ShowDialog(); $dialog.Dispose()
}

function Table([string]$Title,$Columns,$Items) { return @{title=$Title; columns=$Columns; items=@($Items)} }

function Limited-List($List,[string[]]$SearchFields,[string]$Search,$Filters) {
    foreach ($item in $List) {
        $match=$true
        foreach ($field in $Filters.Keys) {
            $criterion=$Filters[$field]
            $value=Get-Val $item $field
            if ($criterion -eq '__has' -and -not $value) { $match=$false }
            elseif ($criterion -eq '__none' -and $value) { $match=$false }
            elseif ($criterion -and $criterion -notin @('__has','__none') -and [string]$criterion -ne [string]$value) { $match=$false }
        }
        $haystack=($SearchFields | ForEach-Object { Get-Val $item $_ }) -join ' '
        if ($match -and (!$Search -or $haystack.IndexOf($Search,[StringComparison]::CurrentCultureIgnoreCase) -ge 0)) { $item }
    }
}

function Refresh-Grid {
    if (!$script:listView) { return }
    $view=$script:listView; $values=@{}
    foreach($key in $view.filters.Keys){ $values[$key]=$view.filters[$key].SelectedItem.key }
    $items=@(Limited-List $view.items $view.fields $view.search.Text.Trim() $values)
    if ($view.dateRange) {
        $from=$view.from.Value.ToString('yyyy-MM-dd'); $to=$view.to.Value.ToString('yyyy-MM-dd')
        $items=@($items | Where-Object { $_.received -ge $from -and $_.received -le $to })
    }
    if ($view.sort) { $items=@($items | Sort-Object -Property $view.sort -Descending:$view.desc) }
    $last=[Math]::Max(0,[Math]::Ceiling($items.Count/20)-1); $view.page=[Math]::Max(0,[Math]::Min($last,$view.page))
    Grid-Data $view.grid @($items | Select-Object -Skip ($view.page*20) -First 20)
    $view.count.Text="Записей: $($items.Count)   •   Страница $($view.page+1) / $($last+1)"
    $view.prev.Enabled=$view.page -gt 0; $view.next.Enabled=$view.page -lt $last
}

function Show-List($Items,$Columns,$FilterFields=@(),[switch]$ReceivedDates) {
    $grid=New-Grid $Columns; $script:pageGrid=$grid
    $searchBar=New-Flow 'Top' 49; $searchBar.AutoScroll=$true
    $search=New-Object Windows.Forms.TextBox; $search.Width=170; $search.Margin=[Windows.Forms.Padding]::new(3,7,11,3)
    $searchBar.Controls.Add((New-Label 'Поиск')); $searchBar.Controls.Add($search)
    $filters=@{}
    foreach($field in $FilterFields){
        $combo=[Windows.Forms.ComboBox]::new(); $combo.Width=126; $combo.DropDownStyle='DropDownList'; $combo.DisplayMember='label'
        $combo.Margin=[Windows.Forms.Padding]::new(3,7,8,3)
        $label=$script:colNames[$field]
        [void]$combo.Items.Add((Option '' "Все · $label"))
        if($field -eq 'last_test'){
            [void]$combo.Items.Add((Option '__has' 'Испытание есть')); [void]$combo.Items.Add((Option '__none' 'Без испытания'))
        }else{
            $choices=@($Items | ForEach-Object { Get-Val $_ $field } | Where-Object { $null -ne $_ -and $_ -ne '' } | Sort-Object -Unique)
            foreach($entry in $choices){ [void]$combo.Items.Add((Option $entry (Display-Val $entry))) }
        }
        $combo.SelectedIndex=0; $filters[$field]=$combo; $searchBar.Controls.Add($combo)
        $combo.Add_SelectedIndexChanged({ $script:listView.page=0; Refresh-Grid })
    }
    $footer=New-Flow 'Bottom' 43
    $count=New-Label ''; $count.Margin=[Windows.Forms.Padding]::new(8,10,10,3)
    $prev=New-Button 'Назад'; $next=New-Button 'Далее'; $footer.Controls.AddRange(@($prev,$next,$count))
    $script:listView=@{ items=@($Items); fields=$Columns; page=0; sort=$null; desc=$false; grid=$grid
        filters=$filters; search=$search; count=$count; prev=$prev; next=$next; dateRange=[bool]$ReceivedDates }
    if($ReceivedDates){
        $dates=New-Flow 'Top' 38
        $from=[Windows.Forms.DateTimePicker]::new(); $to=[Windows.Forms.DateTimePicker]::new()
        foreach($picker in @($from,$to)){ $picker.Format='Short'; $picker.Width=126 }
        $from.Value=$from.Value.AddYears(-1)
        $dates.Controls.AddRange(@((New-Label 'Поступление с'),$from,(New-Label 'по'),$to))
        $script:listView.from=$from; $script:listView.to=$to
        foreach($picker in @($from,$to)){ $picker.Add_ValueChanged({$script:listView.page=0; Refresh-Grid}) }
    }
    $search.Add_TextChanged({ $script:listView.page=0; Refresh-Grid })
    $prev.Add_Click({ $script:listView.page--; Refresh-Grid })
    $next.Add_Click({ $script:listView.page++; Refresh-Grid })
    $grid.Add_ColumnHeaderMouseClick({
        param($sender,$args_)
        $field=$sender.Columns[$args_.ColumnIndex].Name
        $script:listView.desc=($script:listView.sort -eq $field -and -not $script:listView.desc)
        $script:listView.sort=$field; Refresh-Grid
    })
    $script:content.Controls.Add($grid)
    $script:content.Controls.Add($footer)
    if($ReceivedDates){ $script:content.Controls.Add($dates) }
    $script:content.Controls.Add($searchBar)
    Refresh-Grid
}

function Set-Toolbar {
    $script:toolbar=New-Flow 'Top' 55
    $script:toolbar.AutoScroll=$true
    $script:content.Controls.Add($script:toolbar)
    Add-Action $script:toolbar 'Обновить' { Render-Section }
}

function Catalog-Form([string]$Group,$Record=$null,$Product=$null) {
    $look=Invoke-Api 'lookups'
    $id=Get-Val $Record 'id'
    switch($Group) {
        'products' {
            $fields=@(foreach($key in @('code','name','type','format','collection','surface')){
                Field $key $script:colNames[$key] 'text' (Get-Val $Record $key)
            })
            $title='Карточка продукта'
        }
        'orders' {
            if(-not $Product){$Product=Get-Val $Record 'product_id'}
            $due=if($id){$Record.due}else{(Get-Date).AddDays(7).ToString('yyyy-MM-dd')}
            $fields=@((Field 'code' 'Номер заказа' 'text' $Record.code),
                (Field 'product_id' 'Продукт' 'choice' $Product @(Item-Options ($look.products | Where-Object status -eq 'active') 'name' 'code')),
                (Field 'quantity' 'Количество, шт.' 'text' $Record.quantity),(Field 'due' 'Срок (ГГГГ-ММ-ДД)' 'text' $due))
            if($id){
                $fields+=Field 'status' 'Статус' 'choice' $Record.status @((Option 'planned' 'Запланирован'),(Option 'cancelled' 'Отменён'))
            }
            $title='Производственный заказ'
        }
        'equipment_programs' {
            $fields=@((Field 'equipment_id' 'Оборудование' 'choice' $Record.equipment_id @(Item-Options $look.equipment)))
            $fields+=@(foreach($key in @('name','temperature','duration','pressure','notes')){
                Field $key $script:colNames[$key] 'text' (Get-Val $Record $key)
            })
            $title='Программа оборудования'
        }
    }
    $body=Edit-Form $title $fields
    if($null -ne $body) {
        if($id){ [void](Invoke-Api "$Group/$id" 'PATCH' $body) }
        else{ [void](Invoke-Api $Group 'POST' $body) }
        Render-Section
    }
}

function Product-Card($Record) {
    $p=Invoke-Api "products/$($Record.id)"
    $summary="$($p.code) · $($p.name)`r`n$($p.type) · $($p.format) · $($p.surface)`r`nКоллекция: $($p.collection)   Статус: $(Display-Val $p.status)"
    Show-Tables 'Карточка продукта' $summary @(
        (Table 'Рецептуры массы' @('version','status','author','created') @($p.related.recipes|Where-Object kind -eq 'mass')),
        (Table 'Рецептуры глазури' @('version','status','author','created') @($p.related.recipes|Where-Object kind -eq 'glaze')),
        (Table 'Технологические карты' @('name','version','status') $p.related.cards),
        (Table 'Партии' @('code','line','status','current_step') $p.related.batches),
        (Table 'История' @('created','author','action','detail') $p.history))
}

function Edit-Collection([string]$Title,$Columns,$Initial,[scriptblock]$Edit,[scriptblock]$Commit,[string]$Help) {
    $dialog=New-Form $Title 900 490; $dialog.StartPosition='CenterParent'; $dialog.Padding=[Windows.Forms.Padding]::new(15)
    $grid=New-Grid $Columns; $bar=New-Flow 'Top' 46; $footer=New-Flow 'Bottom' 50
    $note=New-Label $Help; $note.Dock='Top'; $note.Padding=[Windows.Forms.Padding]::new(0,7,0,11)
    $items=[Collections.ArrayList]::new(); foreach($i in @($Initial)){ if($i){ [void]$items.Add($i) } }
    $dialog.Controls.AddRange(@($grid,$footer,$bar,$note))
    $dialog.Tag=@{items=$items; grid=$grid; editor=$Edit; commit=$Commit}
    Add-Action $bar 'Добавить' ({
        $context=$dialog.Tag; $new=& $context.editor $null
        if($null -ne $new){ [void]$context.items.Add($new); Grid-Data $context.grid $context.items }
    }.GetNewClosure())
    Add-Action $bar 'Изменить' ({
        $context=$dialog.Tag; $old=Selected $context.grid; $new=& $context.editor $old
        if($null -ne $new){ $context.items[$context.items.IndexOf($old)]=$new; Grid-Data $context.grid $context.items }
    }.GetNewClosure())
    Add-Action $bar 'Удалить' ({
        $context=$dialog.Tag; $old=Selected $context.grid; $context.items.Remove($old)
        Grid-Data $context.grid $context.items
    }.GetNewClosure())
    foreach($direction in @(-1,1)){
        $shift=$direction
        $label=if($shift -lt 0){'Выше'}else{'Ниже'}
        Add-Action $bar $label ({
            $context=$dialog.Tag; $old=Selected $context.grid; $index=$context.items.IndexOf($old); $new=$index+$shift
            if($new -ge 0 -and $new -lt $context.items.Count){
                $context.items.RemoveAt($index); $context.items.Insert($new,$old)
                Grid-Data $context.grid $context.items; $context.grid.Rows[$new].Selected=$true
            }
        }.GetNewClosure())
    }
    Add-Action $footer 'Сохранить' ({
        & $dialog.Tag.commit @($dialog.Tag.items.ToArray())
        $dialog.DialogResult='OK'; $dialog.Close()
    }.GetNewClosure()) -Primary
    $cancel=New-Button 'Отмена'; $cancel.DialogResult='Cancel'; $dialog.CancelButton=$cancel; $footer.Controls.Add($cancel)
    Grid-Data $grid $items
    $result=$dialog.ShowDialog(); $dialog.Dispose()
    return ($result -eq 'OK')
}

function Recipe-Form($Record=$null) {
    $look=Invoke-Api 'lookups'
    $kind=if($script:section -eq 'mass'){'mass'}else{'glaze'}
    $old=if($Record){Invoke-Api "recipes/$($Record.id)"}else{$null}
    if($old -and $old.status -ne 'draft'){throw 'Изменять состав можно только в черновике.'}
    $fields=@()
    if(!$old){$fields+=Field 'product_id' 'Продукт' 'choice' $null @(Item-Options ($look.products | Where-Object status -eq 'active') 'name' 'code')}
    $fields+=Field 'notes' 'Комментарий технолога' 'long' (Get-Val $old 'notes')
    $body=Edit-Form 'Версия рецептуры' $fields 'Состав'
    if($null -eq $body){return}
    $body.kind=$kind
    $editor={
        param($item)
        $entry=Edit-Form 'Компонент' @(
            (Field 'material_id' 'Сырьё' 'choice' (Get-Val $item 'material_id') @(Item-Options $look.materials)),
            (Field 'share' 'Доля, %' 'text' (Get-Val $item 'share')),
            (Field 'tolerance' 'Допуск, %' 'text' $(if($item){$item.tolerance}else{0})))
        if($null -ne $entry){$entry.material=($look.materials | Where-Object id -eq $entry.material_id).name; $entry}
    }.GetNewClosure()
    $commit={
        param($items)
        $body.components=@($items)
        if($old){[void](Invoke-Api "recipes/$($old.id)" 'PATCH' $body)}else{[void](Invoke-Api 'recipes' 'POST' $body)}
    }.GetNewClosure()
    if(Edit-Collection 'Компоненты рецептуры' @('material','share','tolerance') $old.components $editor $commit 'Порядок строк задаёт последовательность загрузки. Для утверждения сумма долей должна быть 100%.'){ Render-Section }
}

function Recipe-Card($Record) {
    $r=Invoke-Api "recipes/$($Record.id)"
    $sum=($r.components|Measure-Object -Property share -Sum).Sum
    Show-Tables 'Рецептура' "$($Record.product) · $(Display-Val $r.kind) · версия $($r.version)`r`n$(Display-Val $r.status) · $($Record.author) · $($r.created)`r`nСумма долей: $sum% · $($r.notes)" @(
        (Table 'Компоненты' @('position','material','share','tolerance') $r.components),
        (Table 'История' @('created','author','action','detail') $r.history))
}

function Edit-Step($Step,$Look) {
    $choice=@((Option '' 'Без оборудования')) + @(Item-Options $Look.equipment)
    $stage=Edit-Form 'Шаг технологической карты' @(
        (Field 'name' 'Название операции' 'text' (Get-Val $Step 'name')),
        (Field 'kind' 'Тип шага' 'choice' (Get-Val $Step 'kind') @('Смешивание','Формование','Сушка','Глазурование','Обжиг','Контроль' | ForEach-Object {Option $_ $_})),
        (Field 'equipment_id' 'Оборудование' 'choice' (Get-Val $Step 'equipment_id') $choice),
        (Field 'required' 'Обязательный' 'choice' $(if($Step){$Step.required}else{1}) @((Option 1 'Да'),(Option 0 'Нет'))),
        (Field 'instructions' 'Инструкция' 'long' (Get-Val $Step 'instructions'))) 'Параметры'
    if($null -eq $stage){return}
    $stage.equipment=if($stage.equipment_id){($Look.equipment|Where-Object id -eq $stage.equipment_id).name}else{''}
    $paramFields=@('name','unit','target','minimum','maximum')
    $columnNames=$script:colNames
    $parameter={
        param($item)
        $fields=@(foreach($key in $paramFields){ Field $key $columnNames[$key] 'text' (Get-Val $item $key) })
        $fields+=Field 'required' 'Обязательный' 'choice' $(if($item){$item.required}else{1}) @((Option 1 'Да'),(Option 0 'Нет'))
        Edit-Form 'Нормативный параметр' $fields
    }.GetNewClosure()
    $commit={param($argsForStep) $stage.parameters=@($argsForStep)}.GetNewClosure()
    if(Edit-Collection 'Параметры шага' $paramFields (Get-Val $Step 'parameters') $parameter $commit 'Укажите плановое значение и границы допустимого диапазона.'){return $stage}
}

function Card-Form($Record=$null) {
    $look=Invoke-Api 'lookups'
    $old=if($Record){Invoke-Api "tech_cards/$($Record.id)"}else{$null}
    if($old -and $old.status -ne 'draft'){throw 'Менять шаги можно только в черновике.'}
    $fields=@()
    if(!$old){$fields+=Field 'product_id' 'Продукт' 'choice' $null @(Item-Options ($look.products|Where-Object status -eq 'active') 'name' 'code')}
    $fields+=Field 'name' 'Наименование карты' 'text' (Get-Val $old 'name')
    $body=Edit-Form 'Технологическая карта' $fields 'Шаги'
    if($null -eq $body){return}
    $editor={param($step) Edit-Step $step $look}.GetNewClosure()
    $commit={
        param($items) $body.steps=@($items)
        if($old){[void](Invoke-Api "tech_cards/$($old.id)" 'PATCH' $body)}else{[void](Invoke-Api 'tech_cards' 'POST' $body)}
    }.GetNewClosure()
    if(Edit-Collection 'Маршрут технологической карты' @('name','kind','equipment','required','instructions') $old.steps $editor $commit 'Строки выполняются по порядку. Порядок можно изменить кнопками «Выше» и «Ниже».'){Render-Section}
}

function Card-View($Record) {
    $card=Invoke-Api "tech_cards/$($Record.id)"
    $parameters=@(foreach($step in $card.steps){ foreach($p in $step.parameters){ $p | Add-Member -NotePropertyName step -NotePropertyValue $step.name -PassThru } })
    Show-Tables 'Технологическая карта' "$($Record.product) · $($card.name)`r`nВерсия $($card.version) · $(Display-Val $card.status)" @(
        (Table 'Маршрут' @('position','name','kind','equipment','required','instructions') $card.steps),
        (Table 'Параметры' @('step','name','unit','target','minimum','maximum','required') $parameters),
        (Table 'История' @('created','author','action') $card.history))
}

function Publish-Selected([string]$Group,[string]$Action) {
    $item=Selected $script:pageGrid
    if($Action -eq 'approve'){
        $choice=[Windows.Forms.MessageBox]::Show('Утвердить версию? Предыдущая действующая версия уйдёт в архив.',
            'Утверждение', [Windows.Forms.MessageBoxButtons]::YesNo)
        if($choice -ne 'Yes'){return}
    }
    [void](Invoke-Api "$Group/$($item.id)/$Action" 'POST' @{})
    Render-Section
}

function Batch-Form($Order=$null) {
    $look=Invoke-Api 'lookups'
    $lines=@($look.equipment | Select-Object -ExpandProperty line -Unique | Sort-Object)
    $body=Edit-Form 'Новая производственная партия' @(
        (Field 'code' 'Номер партии'),
        (Field 'order_id' 'Производственный заказ' 'choice' (Get-Val $Order 'id') @(Item-Options ($look.orders|Where-Object status -in @('planned','in_progress')) 'product' 'code')),
        (Field 'line' 'Линия' 'choice' $null @($lines|ForEach-Object{Option $_ $_})),
        (Field 'quantity' 'Количество, шт.' 'text' (Get-Val $Order 'quantity'))) 'Сформировать'
    if($null -eq $body){return}
    $batch=Invoke-Api 'batches' 'POST' $body
    Batch-View $batch
    Render-Section
}

function Batch-View($Record) {
    $batch=Invoke-Api "batches/$($Record.id)"
    $summary="$($batch.code) · $($batch.product) · $($batch.line)`r`n$(Display-Val $batch.status) · Заказ $($batch.order_code) · $($batch.quantity) шт.`r`nРецептуры: масса v$($batch.mass_version), глазурь v$($batch.glaze_version). Карта v$($batch.card_version)."
    $parameters=@(foreach($step in $batch.steps){ foreach($p in $step.parameters){ $p | Add-Member -NotePropertyName step -NotePropertyValue $step.name -PassThru } })
    Show-Tables 'Производственная партия' $summary @(
        (Table 'Маршрут' @('position','name','status','started','finished','equipment','comment') $batch.steps),
        (Table 'Фактические параметры' @('step','name','unit','target','minimum','maximum','value') $parameters),
        (Table 'Сырьё' @('code','material','quantity','unit','status') $batch.raw),
        (Table 'Программы' @('name','equipment','temperature','duration','pressure') $batch.programs),
        (Table 'Инциденты' @('severity','description','state','created','resolution') $batch.incidents),
        (Table 'Отклонения' @('step','parameter','target','value','unit','comment') $batch.deviations),
        (Table 'Журнал' @('created','author','action','detail') $batch.events))
}

function Batch-Configure([string]$Action) {
    $batch=Selected $script:pageGrid
    if($batch.status -ne 'planned'){throw 'Комплектацию можно изменить до запуска.'}
    $look=Invoke-Api 'lookups'
    if($Action -eq 'raw'){
        $body=Edit-Form "Сырьё · $($batch.code)" @(
            (Field 'raw_lot_id' 'Допущенная партия сырья' 'choice' $null @(Item-Options ($look.raw_lots|Where-Object status -eq 'released') 'material' 'code')),
            (Field 'quantity' 'Количество, кг'))
    }else{
        $body=Edit-Form "Программа · $($batch.code)" @(
            (Field 'program_id' 'Программа оборудования' 'choice' $null @(Item-Options ($look.programs|Where-Object line -eq $batch.line) 'name' 'equipment')))
    }
    if($null -eq $body){return}
    [void](Invoke-Api "batches/$($batch.id)/$Action" 'POST' $body)
    Render-Section
}

function Report-View {
    $script:reportNames=[ordered]@{batches='Партии за период';deviations='Отклонения';recipes='Использование рецептур';firing='Обжиг и телеметрия';blocks='Лабораторные блокировки'}
    $script:reportColumns=@{
        batches=@('code','product','created','status','deviation','decision')
        deviations=@('batch','step','parameter','target','value','severity','comment','created')
        recipes=@('product','kind','version','batches','quantity')
        firing=@('batch','zone','parameter','value','target','deviation','created')
        blocks=@('batch','product','created','comment','author')
    }
    $bar=New-Flow 'Top' 49
    $script:reportType=[Windows.Forms.ComboBox]::new(); $script:reportType.Width=225
    $script:reportType.DropDownStyle='DropDownList'; $script:reportType.DisplayMember='label'
    foreach($key in $script:reportNames.Keys){[void]$script:reportType.Items.Add((Option $key $script:reportNames[$key]))}
    $script:reportType.SelectedIndex=0
    $script:reportStart=[Windows.Forms.DateTimePicker]::new(); $script:reportEnd=[Windows.Forms.DateTimePicker]::new()
    $script:reportStart.Value=(Get-Date).AddDays(-30)
    foreach($p in @($script:reportStart,$script:reportEnd)){$p.Format='Short';$p.Width=120}
    $bar.Controls.AddRange(@($script:reportType,(New-Label 'С'),$script:reportStart,(New-Label 'по'),$script:reportEnd))
    Add-Action $bar 'Сформировать' { Fetch-Report } -Primary
    Add-Action $bar 'Экспорт CSV' {
        $save=[Windows.Forms.SaveFileDialog]::new(); $save.Filter='CSV (*.csv)|*.csv';$save.FileName="ceramika-$($script:reportKey).csv"
        if($save.ShowDialog() -eq 'OK'){
            Invoke-WebRequest -UseBasicParsing -TimeoutSec 8 -Uri ($script:apiBase+$script:reportPath+'&format=csv') -Headers @{Authorization="Bearer $script:token"} -OutFile $save.FileName
        }
        $save.Dispose()
    }
    $script:reportPane=[Windows.Forms.Panel]::new(); $script:reportPane.Dock='Fill'
    $script:content.Controls.AddRange(@($script:reportPane,$bar))
    Fetch-Report
}

function Fetch-Report {
    $key=$script:reportType.SelectedItem.key
    $from=$script:reportStart.Value.ToString('yyyy-MM-dd'); $to=$script:reportEnd.Value.ToString('yyyy-MM-dd')
    $path="reports/$($key)?from=$from&to=$to"
    $items=@(Invoke-Api $path)
    foreach($control in @($script:reportPane.Controls)){ $control.Dispose() }
    $grid=New-Grid $script:reportColumns[$key]; Grid-Data $grid $items; $script:reportPane.Controls.Add($grid)
    $script:reportKey=$key; $script:reportPath=$path
}

function Dashboard {
    $products=@(Invoke-Api 'products'); $recipes=@(Invoke-Api 'recipes'); $cards=@(Invoke-Api 'tech_cards')
    $orders=@(Invoke-Api 'orders'); $batches=@(Invoke-Api 'batches'); $events=@(Invoke-Api 'events')
    $metrics=[Windows.Forms.TableLayoutPanel]::new();$metrics.Dock='Top';$metrics.ColumnCount=4;$metrics.RowCount=2;$metrics.Height=183
    foreach($i in 0..3){[void]$metrics.ColumnStyles.Add([Windows.Forms.ColumnStyle]::new('Percent',25))}
    foreach($i in 0..1){[void]$metrics.RowStyles.Add([Windows.Forms.RowStyle]::new('Percent',50))}
    $indicators=@(
        @('Активная продукция',@($products|Where-Object status -eq 'active').Count,'products','active'),
        @('Рецептуры массы',@($recipes|Where-Object { $_.kind -eq 'mass' -and $_.status -eq 'active' }).Count,'mass','active'),
        @('Рецептуры глазури',@($recipes|Where-Object { $_.kind -eq 'glaze' -and $_.status -eq 'active' }).Count,'glaze','active'),
        @('Технологические карты',@($cards|Where-Object status -eq 'active').Count,'cards','active'),
        @('Заказы в работе',@($orders|Where-Object status -eq 'in_progress').Count,'orders','in_progress'),
        @('Партии в работе',@($batches|Where-Object status -eq 'in_progress').Count,'batches','in_progress'),
        @('Партии с отклонениями',@($batches|Where-Object { $_.warning -or $_.critical }).Count,'batches','deviations'),
        @('Ожидают решения',@($batches|Where-Object status -eq 'quality').Count,'batches','quality'))
    for($i=0;$i -lt $indicators.Count;$i++){
        $metric=$indicators[$i]
        $btn=New-Button "$($metric[1])`r`n$($metric[0])";$btn.Dock='Fill'
        $btn.TextAlign='MiddleLeft'; $btn.Font=[Drawing.Font]::new('Segoe UI',11,[Drawing.FontStyle]::Bold)
        $btn.Tag=@{section=$metric[2];status=$metric[3]}
        $btn.Add_Click({param($sender,$e)
            $script:section=$sender.Tag.section; $script:quickFilter=$sender.Tag.status; Run-Safely { Render-Section }
        })
        $metrics.Controls.Add($btn,($i%4),[int][Math]::Floor($i/4))
    }
    $recent=New-Grid @('created','action','detail','author')
    Grid-Data $recent @($events|Select-Object -First 20)
    $recent.Add_CellDoubleClick({param($sender,$e) if ($e.RowIndex -ge 0) {
        $item=$sender.Rows[$e.RowIndex].Tag
        if($item.batch_id){Run-Safely {Batch-View ([pscustomobject]@{id=$item.batch_id})}}
    }})
    $label=New-Label 'Последние производственные события' 13 -Bold;$label.Dock='Top'
    $label.Padding=[Windows.Forms.Padding]::new(3,10,0,9)
    $script:content.Controls.AddRange(@($recent,$label,$metrics))
}

function Lab-Target($Record) {
    $kind=$script:section.Replace('_lab','')
    $result=Invoke-Api "lab/targets/$kind/$($Record.id)"
    $t=$result.target
    if($kind -eq 'raw'){
        $summary="$($t.code) · $($t.material) ($($t.category))`r`n$($t.supplier) · $($t.supplier_code) · $($t.received)`r`n$($t.quantity) $($t.unit) · $($t.location) · $(Display-Val $t.status)"
    }else{
        $summary="$($t.code) · $($t.product) · $($t.line)`r`n$(Display-Val $t.status) · $(Display-Val $t.decision)"
    }
    $last=$result.decisions | Select-Object -First 1
    if($last){
        $summary+="`r`nРешение: $(Display-Val $last.decision) · $($last.created) · $($last.author)`r`n$($last.comment)"
    }
    $dialog=New-Form "Карточка контроля · $($t.code)" 1000 500; $dialog.Padding=[Windows.Forms.Padding]::new(16)
    $dialog.StartPosition='CenterParent'
    $header=[Windows.Forms.TextBox]::new();$header.Multiline=$true;$header.ReadOnly=$true
    $header.Text=$summary;$header.Height=132;$header.Dock='Top';$header.ScrollBars='Vertical'
    $grid=New-Grid @('id','type','appointed','analyst','priority','status','result','finished')
    Grid-Data $grid $result.tests
    $buttons=New-Flow 'Bottom' 45
    Add-Action $buttons 'Открыть испытание' ({Show-Protocol (Selected $grid).id; $dialog.Close()}.GetNewClosure()) -Primary
    $grid.Add_CellDoubleClick({param($sender,$e) if($e.RowIndex -ge 0){Run-Safely {Show-Protocol $sender.Rows[$e.RowIndex].Tag.id; $sender.FindForm().Close()}}})
    Add-Action $buttons 'Назначить испытание' ({Lab-Assign $t; $dialog.Close()}.GetNewClosure())
    $tabs=[Windows.Forms.TabControl]::new();$tabs.Dock='Fill'
    $testsPage=[Windows.Forms.TabPage]::new('Испытания');$testsPage.Controls.Add($grid);$tabs.TabPages.Add($testsPage)
    $historyPage=[Windows.Forms.TabPage]::new('История решений')
    $decisions=New-Grid @('created','author','decision','comment')
    Grid-Data $decisions $result.decisions
    $historyPage.Controls.Add($decisions);$tabs.TabPages.Add($historyPage)
    $dialog.Controls.AddRange(@($tabs,$buttons,$header));[void]$dialog.ShowDialog();$dialog.Dispose()
    Render-Section
}

function Lab-Assign($Target) {
    $kind=$script:section.Replace('_lab','')
    $look=Invoke-Api 'lookups'; $specs=@(Invoke-Api "lab/specs/$kind")
    $fields=@(
        (Field 'target_code' 'Партия' 'read' "$($Target.code) · $($Target.material)$($Target.product)"),
        (Field 'type' 'Вид испытания' 'choice' 'Основное' @((Option 'Основное' 'Основное'),(Option 'Повторное' 'Повторное'))),
        (Field 'appointed' 'Назначено (UTC)' 'text' ((Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss'))),
        (Field 'analyst_id' 'Исполнитель' 'choice' $script:user.id @(Item-Options $look.analysts)),
        (Field 'priority' 'Приоритет' 'choice' 'Обычный' @((Option 'Обычный' 'Обычный'),(Option 'Высокий' 'Высокий'))),
        (Field 'comment' 'Комментарий' 'long'))
    foreach($spec in $specs){
        $label="$($spec.name), $($spec.unit) · $($spec.minimum)…$($spec.maximum)"
        if($spec.required){ $fields+=Field "sp-$($spec.id)" $label 'read' 'Обязательный параметр' }
        else{ $fields+=Field "sp-$($spec.id)" $label 'choice' $spec.id @((Option $spec.id 'Включить'),(Option '' 'Исключить')) }
    }
    $body=Edit-Form 'Назначение испытания' $fields 'Назначить'
    if($null -eq $body){return}
    $body.spec_ids=@(foreach($spec in $specs){if($body["sp-$($spec.id)"]){$spec.id}})
    $body.kind=$kind; $body.target=$Target.id
    $test=Invoke-Api 'lab/tests' 'POST' $body
    Show-Protocol $test.id
    Render-Section
}

function Show-Protocol([int]$Id) {
    $lab=Invoke-Api "lab/tests/$Id"
    $dialog=New-Form "Испытание №$Id" 920 540;$dialog.Padding=[Windows.Forms.Padding]::new(16);$dialog.StartPosition='CenterParent'
    $title=New-Label "Испытание №$Id  ·  $(Display-Val $lab.kind)  ·  $(Display-Val $lab.status)" 16 -Bold
    $heading=[Windows.Forms.TextBox]::new();$heading.Multiline=$true;$heading.ReadOnly=$true;$heading.Dock='Top';$heading.Height=75
    $heading.Text="$($lab.type) · $($lab.analyst) · $(Display-Val $lab.result)`r`nНазначено $($lab.appointed) · Приоритет: $($lab.priority)`r`n$($lab.comment)"
    $title.Dock='Top';$title.Padding=[Windows.Forms.Padding]::new(0,0,0,10)
    $tabs=[Windows.Forms.TabControl]::new();$tabs.Dock='Fill'
    foreach($table in @((Table 'Измерения' @('name','unit','minimum','maximum','required','value') $lab.parameters),
        (Table 'Решения' @('created','author','decision','comment') $lab.decisions))){
        $page=[Windows.Forms.TabPage]::new($table.title);$grid=New-Grid $table.columns; Grid-Data $grid $table.items
        $page.Controls.Add($grid);$tabs.TabPages.Add($page)
    }
    $bar=New-Flow 'Bottom' 45
    if($lab.status -eq 'open'){
        Add-Action $bar 'Ввести результаты' ({
            $fields=@(foreach($spec in $lab.parameters){
                $star=if($spec.required){' *'}else{''}
                Field ([string]$spec.id) "$($spec.name)$star · $($spec.minimum)…$($spec.maximum) $($spec.unit)" 'text' $spec.value
            })
            $fields+=Field 'operation' 'Действие' 'choice' 'save' @((Option 'save' 'Сохранить промежуточно'),(Option 'finish' 'Завершить испытание'))
            $body=Edit-Form "Измерения · №$Id" $fields 'Применить'
            if($null -eq $body){return}
            $op=$body.operation;$body.Remove('operation')
            [void](Invoke-Api "lab/tests/$Id/$op" 'POST' @{values=$body})
            $dialog.Close();Show-Protocol $Id
        }.GetNewClosure()) -Primary
    } elseif(-not @($lab.decisions|Where-Object{$_}).Count){
        Add-Action $bar 'Принять решение' ({
            $body=Edit-Form "Решение · №$Id" @(
                (Field 'decision' 'Итог' 'choice' $null @((Option 'released' 'Разрешить использование'),(Option 'blocked' 'Заблокировать'))),
                (Field 'comment' 'Причина / комментарий' 'long')) 'Применить' 'Для блокировки обязательно укажите причину.'
            if($null -eq $body){return}
            [void](Invoke-Api "lab/tests/$Id/decide" 'POST' $body)
            $dialog.Close();Show-Protocol $Id
        }.GetNewClosure()) -Primary
    }
    if($lab.status -eq 'done'){
        Add-Action $bar 'Сохранить протокол CSV' ({
            $save=[Windows.Forms.SaveFileDialog]::new();$save.Filter='CSV (*.csv)|*.csv';$save.FileName="protocol-$Id.csv"
            if($save.ShowDialog() -eq 'OK'){
                $lines=foreach($spec in $lab.parameters){[pscustomobject][ordered]@{
                    'Протокол'=$Id;'Вид'=Display-Val $lab.kind;'Исполнитель'=$lab.analyst;'Дата'=$lab.finished
                    'Параметр'=$spec.name;'Единица'=$spec.unit;'Минимум'=$spec.minimum;'Максимум'=$spec.maximum
                    'Факт'=$spec.value;'Результат'=Display-Val $lab.result
                    'Решение'=Display-Val ($lab.decisions|Select-Object -First 1 -ExpandProperty decision)
                }}
                $lines | Export-Csv -LiteralPath $save.FileName -NoTypeInformation -Delimiter ';' -Encoding UTF8
            }
            $save.Dispose()
        }.GetNewClosure())
    }
    $dialog.Controls.AddRange(@($tabs,$bar,$heading,$title));[void]$dialog.ShowDialog();$dialog.Dispose()
}

function Bind-Open([scriptblock]$Action) {
    $script:pageGrid.Tag=$Action
    $script:pageGrid.Add_CellDoubleClick({param($sender,$e)
        if($e.RowIndex -ge 0){ Run-Safely { & $sender.Tag $sender.Rows[$e.RowIndex].Tag } }
    })
}

function Lab-OpenSelected([switch]$Assign,$Record=$null){
    if(!$Record){$Record=Selected $script:pageGrid}
    if($Assign){Lab-Assign $Record}else{Lab-Target $Record}
}

function Render-Section {
    $script:title.Text=$script:sections[$script:section]
    foreach($button in $script:sidebar.Controls){
        if($button -is [Windows.Forms.Button]){
            $selected=$button.Tag -eq $script:section
            $button.BackColor=if($selected){[Drawing.ColorTranslator]::FromHtml('#28434D')}else{$script:nav}
            $button.ForeColor=if($selected){$script:accent}else{[Drawing.Color]::White}
        }
    }
    $script:listView=$null;$script:pageGrid=$null
    foreach($control in @($script:content.Controls)){ $control.Dispose() }
    switch($script:section){
        'home' { Dashboard }
        'products' {
            Show-List @(Invoke-Api 'products') @('code','name','type','format','surface','status','mass','glaze','card') @('type','format','status')
            Set-Toolbar
            Add-Action $script:toolbar 'Новый продукт' {Catalog-Form 'products'} -Primary
            Add-Action $script:toolbar 'Карточка' {Product-Card (Selected $script:pageGrid)}
            Add-Action $script:toolbar 'Изменить' {Catalog-Form 'products' (Selected $script:pageGrid)}
            Add-Action $script:toolbar 'Архивировать' {$r=Selected $script:pageGrid;[void](Invoke-Api "products/$($r.id)" 'DELETE');Render-Section}
            Add-Action $script:toolbar 'Создать заказ' {Catalog-Form 'orders' $null (Selected $script:pageGrid).id}
            Bind-Open {param($r) Product-Card $r}
        }
        {$_ -in @('mass','glaze')} {
            Show-List @(Invoke-Api 'recipes'|Where-Object kind -eq $script:section) @('product','kind','version','status','author','created','notes') @('product','status','version')
            Set-Toolbar
            Add-Action $script:toolbar 'Новая версия' {Recipe-Form} -Primary
            Add-Action $script:toolbar 'Карточка' {Recipe-Card (Selected $script:pageGrid)}
            Add-Action $script:toolbar 'Изменить' {Recipe-Form (Selected $script:pageGrid)}
            Add-Action $script:toolbar 'На согласование' {Publish-Selected 'recipes' 'review'}
            Add-Action $script:toolbar 'Утвердить' {Publish-Selected 'recipes' 'approve'}
            Add-Action $script:toolbar 'На доработку' {Publish-Selected 'recipes' 'rework'}
            Add-Action $script:toolbar 'В архив' {Publish-Selected 'recipes' 'archive'}
            Bind-Open {param($r) Recipe-Card $r}
        }
        'cards' {
            Show-List @(Invoke-Api 'tech_cards') @('name','product','version','status') @('product','status','version')
            Set-Toolbar
            Add-Action $script:toolbar 'Новая карта' {Card-Form} -Primary
            Add-Action $script:toolbar 'Карточка' {Card-View (Selected $script:pageGrid)}
            Add-Action $script:toolbar 'Изменить' {Card-Form (Selected $script:pageGrid)}
            Add-Action $script:toolbar 'Утвердить' {Publish-Selected 'tech_cards' 'approve'}
            Add-Action $script:toolbar 'В архив' {Publish-Selected 'tech_cards' 'archive'}
            Bind-Open {param($r) Card-View $r}
        }
        'orders' {
            Show-List @(Invoke-Api 'orders') @('code','product','quantity','due','status') @('product','status')
            Set-Toolbar
            Add-Action $script:toolbar 'Новый заказ' {Catalog-Form 'orders'} -Primary
            Add-Action $script:toolbar 'Изменить' {Catalog-Form 'orders' (Selected $script:pageGrid)}
            Add-Action $script:toolbar 'Сформировать партию' {Batch-Form (Selected $script:pageGrid)}
        }
        'batches' {
            $items=@(Invoke-Api 'batches')
            if($script:quickFilter -eq 'deviations'){ $items=@($items|Where-Object { $_.warning -or $_.critical }) }
            Show-List $items @('code','product','line','status','current_step','done','total','warning','critical') @('status','line','product')
            Set-Toolbar
            Add-Action $script:toolbar 'Новая партия' {Batch-Form} -Primary
            Add-Action $script:toolbar 'Карточка' {Batch-View (Selected $script:pageGrid)}
            Add-Action $script:toolbar 'Добавить сырьё' {Batch-Configure 'raw'}
            Add-Action $script:toolbar 'Назначить программу' {Batch-Configure 'program'}
            Add-Action $script:toolbar 'Запустить' {$r=Selected $script:pageGrid;[void](Invoke-Api "batches/$($r.id)/launch" 'POST' @{});Render-Section}
            Bind-Open {param($r) Batch-View $r}
        }
        'programs' {
            Show-List @(Invoke-Api 'equipment_programs') @('name','equipment','line','temperature','duration','pressure','notes') @('line','equipment')
            Set-Toolbar
            Add-Action $script:toolbar 'Новая программа' {Catalog-Form 'equipment_programs'} -Primary
            Add-Action $script:toolbar 'Изменить' {Catalog-Form 'equipment_programs' (Selected $script:pageGrid)}
        }
        'incidents' {
            Show-List @(Invoke-Api 'incidents') @('batch','severity','state','description','author','created','resolution') @('severity','state')
            Set-Toolbar
            Add-Action $script:toolbar 'Устранить инцидент' {
                $r=Selected $script:pageGrid
                $body=Edit-Form 'Устранение инцидента' @((Field 'resolution' 'Зафиксируйте решение' 'long'))
                if($null -ne $body){[void](Invoke-Api "incidents/$($r.id)/resolve" 'POST' $body);Render-Section}
            } -Primary
            Add-Action $script:toolbar 'Параметры вне допуска' {
                Show-Tables 'Производственные отклонения' 'Факты за пределами допусков технологической карты' @(
                    (Table 'Отклонения' @('batch','step','parameter','target','value','comment','created') @(Invoke-Api 'reports/deviations')))
            }
            Add-Action $script:toolbar 'Журнал событий' {Show-Tables 'Журнал производства' 'Последние 100 событий' @((Table 'События' @('created','action','detail','author') @(Invoke-Api 'events')))}
        }
        'reports' { Report-View }
        {$_ -in @('raw','mass_lab','glaze_lab','finished')} {
            $kind=$script:section.Replace('_lab','')
            $items=@(Invoke-Api "lab/queue/$kind")
            if($kind -eq 'raw'){
                Show-List $items @('code','supplier_code','material','category','supplier','received','quantity','unit','status','last_test') @('status','supplier','last_test') -ReceivedDates
            }else{
                Show-List $items @('code','product','line','status','decision','last_test') @('status','line','last_test')
            }
            Set-Toolbar
            Add-Action $script:toolbar 'Открыть карточку' {Lab-OpenSelected} -Primary
            Add-Action $script:toolbar 'Назначить испытание' {Lab-OpenSelected -Assign}
            Bind-Open {param($r) Lab-OpenSelected -Record $r}
        }
        'protocols' {
            Show-List @(Invoke-Api 'lab/protocols') @('id','target','kind','type','analyst','result','finished') @('kind','result')
            Set-Toolbar;Add-Action $script:toolbar 'Открыть протокол' {Show-Protocol (Selected $script:pageGrid).id} -Primary
            Bind-Open {param($r) Show-Protocol $r.id}
        }
    }
    if($script:quickFilter -and $script:listView -and $script:listView.filters.ContainsKey('status')){
        $combo=$script:listView.filters.status
        for($i=0;$i -lt $combo.Items.Count;$i++){ if($combo.Items[$i].key -eq $script:quickFilter){$combo.SelectedIndex=$i;break} }
    }
    $script:quickFilter=$null
}

function Build-Workspace {
    $script:sections=if($Module -eq 'tech'){
        [ordered]@{home='Главная';products='Продукция';mass='Рецептуры массы';glaze='Рецептуры глазури';cards='Технологические карты';
        orders='Производственные заказы';batches='Производственные партии';programs='Программы оборудования';incidents='Отклонения и события';reports='Отчёты'}
    }else{
        [ordered]@{raw='Партии сырья';mass_lab='Керамическая масса';glaze_lab='Глазурь';finished='Готовая продукция';protocols='Архив протоколов'}
    }
    $script:section=if($Module -eq 'tech'){'home'}else{'raw'}
    $form=New-Form "Ceramika · $script:moduleName" 1280 780
    $form.MinimumSize=[Drawing.Size]::new(980,600)
    $script:sidebar=New-Flow 'Left' 785;$script:sidebar.Width=230;$script:sidebar.FlowDirection='TopDown'
    $script:sidebar.Padding=[Windows.Forms.Padding]::new(12,18,6,10);$script:sidebar.BackColor=$script:nav;$script:sidebar.AutoScroll=$true
    $brand=New-Label 'CERAMIKA' 18 -Bold;$brand.ForeColor=$script:accent;$brand.Margin=[Windows.Forms.Padding]::new(8,1,0,3)
    $sub=New-Label $script:moduleName 9;$sub.ForeColor=[Drawing.Color]::Gainsboro;$sub.Margin=[Windows.Forms.Padding]::new(8,0,0,24)
    $script:sidebar.Controls.AddRange(@($brand,$sub))
    foreach($section in $script:sections.Keys){
        $button=New-Button $script:sections[$section];$button.Tag=$section;$button.AutoSize=$false;$button.Size=[Drawing.Size]::new(201,40)
        $button.FlatAppearance.BorderSize=0;$button.TextAlign='MiddleLeft'
        $button.Add_Click({param($sender,$e) $script:section=$sender.Tag; Run-Safely {Render-Section}})
        $script:sidebar.Controls.Add($button)
    }
    $workspace=[Windows.Forms.Panel]::new();$workspace.Dock='Fill';$workspace.Padding=[Windows.Forms.Padding]::new(24,14,24,15)
    $header=[Windows.Forms.TableLayoutPanel]::new();$header.Dock='Top';$header.Height=72;$header.ColumnCount=2
    [void]$header.ColumnStyles.Add([Windows.Forms.ColumnStyle]::new('Percent',53))
    [void]$header.ColumnStyles.Add([Windows.Forms.ColumnStyle]::new('Percent',47))
    $script:title=New-Label '' 20 -Bold;$script:title.Margin=[Windows.Forms.Padding]::new(0,9,0,0)
    $account=New-Flow 'Fill' 60;$account.FlowDirection='RightToLeft';$account.Margin=[Windows.Forms.Padding]::new(0,8,0,0)
    $identity=New-Label "$($script:user.name)`r`n$($script:user.role_name) · $($script:user.department)" 9
    $profile=New-Button 'Профиль';$initials=($script:user.name.Split(' ')|Select-Object -First 2|ForEach-Object{$_.Substring(0,1)}) -join ''
    $profile.Text="$initials  ·  Профиль";$profile.BackColor=[Drawing.ColorTranslator]::FromHtml('#DBE7E7')
    $menu=[Windows.Forms.ContextMenuStrip]::new()
    $view=$menu.Items.Add('Просмотр профиля');$change=$menu.Items.Add('Смена пароля');$out=$menu.Items.Add('Выйти')
    $view.Add_Click({
        [void][Windows.Forms.MessageBox]::Show("$($script:user.name)`r`n$($script:user.role_name)`r`n$($script:user.department)`r`nЛогин: $($script:user.login)",'Профиль')
    })
    $change.Add_Click({Run-Safely {
        $data=Edit-Form 'Смена пароля' @((Field 'current' 'Текущий пароль' 'password'),(Field 'password' 'Новый пароль' 'password'))
        if($null -ne $data){[void](Invoke-Api 'password' 'POST' $data); [void][Windows.Forms.MessageBox]::Show('Пароль обновлён.','Ceramika')}
    }})
    $out.Add_Click({$script:restartLogin=$true; $script:mainForm.Close()})
    $profile.ContextMenuStrip=$menu
    $profile.Add_Click({ param($sender,$e) $sender.ContextMenuStrip.Show($sender,0,$sender.Height) })
    $account.Controls.AddRange(@($profile,$identity));$header.Controls.Add($script:title,0,0);$header.Controls.Add($account,1,0)
    $script:content=[Windows.Forms.Panel]::new();$script:content.Dock='Fill'
    $workspace.Controls.AddRange(@($script:content,$header))
    $form.Controls.AddRange(@($workspace,$script:sidebar))
    $script:mainForm=$form
    Render-Section
    return $form
}

$expectedRole=if($Module -eq 'tech'){'technologist'}else{'lab'}
if($Smoke){
    $auth=Invoke-Api 'login' 'POST' @{login=$Module;password='Ceramika2026';role=$expectedRole}
    $script:user=$auth.user;$script:token=$auth.token
    $window=Build-Workspace
    $window.Show()
    [Windows.Forms.Application]::DoEvents()
    foreach($key in $script:sections.Keys){$script:section=$key;Render-Section;[Windows.Forms.Application]::DoEvents()}
    [void](Invoke-Api 'logout' 'POST' @{})
    $window.Close();$window.Dispose()
    Write-Output "WinForms $Module passed all workspace sections"
    return
}

$script:restartLogin=$true
while($script:restartLogin){
    $script:restartLogin=$false
    $demo=$false
    try{$demo=(Invoke-Api 'health').mode -eq 'demo'}catch{}
    $hint=if($demo){"Демо: логин $Module, пароль Ceramika2026."}else{'Введите учётные данные своего рабочего места.'}
    while($true){
        $data=Edit-Form "Ceramika · $script:moduleName" @(
            (Field 'login' 'Логин' 'text' $(if($demo){$Module}else{''})),
            (Field 'password' 'Пароль' 'password')) 'Войти' $hint
        if($null -eq $data){return}
        $data.role=$expectedRole
        try{
            $auth=Invoke-Api 'login' 'POST' $data
            $script:user=$auth.user;$script:token=$auth.token
            break
        }catch{
            [void][Windows.Forms.MessageBox]::Show($_.Exception.Message,'Вход в Ceramika')
        }
    }
    Run-Safely {
        $window=Build-Workspace
        [void]$window.ShowDialog()
        $window.Dispose()
    }
    try{[void](Invoke-Api 'logout' 'POST' @{})}catch{}
    $script:token=$null;$script:user=$null
}
